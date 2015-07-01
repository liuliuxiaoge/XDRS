"""
若干通用方法；
"""

import contextlib
import hashlib
import hmac
import inspect
import multiprocessing
import pyclbr
import random
import shutil
import tempfile
import grp
import pwd
import errno
import fcntl
import os
import sys
import functools
from optparse import OptionParser
from urlparse import urlparse as stdlib_urlparse, ParseResult
import itertools
import xdrs

from oslo.config import cfg
from oslo import messaging
import six

from xdrs import exception
from xdrs.openstack.common import gettextutils
from xdrs.openstack.common.gettextutils import _
from xdrs.openstack.common import importutils
from xdrs.openstack.common import log as logging
from xdrs.openstack.common import processutils

notify_decorator = 'xdrs.notifications.notify_decorator'

CONF = cfg.CONF
CONF.import_opt('instance_usage_audit_period', 'xdrs.service')
CONF.import_opt('password_length', 'xdrs.service')
CONF.import_opt('monkey_patch', 'xdrs.service')
CONF.import_opt('monkey_patch_modules', 'xdrs.service')

LOG = logging.getLogger(__name__)

# used in limits
TIME_UNITS = {
    'SECOND': 1,
    'MINUTE': 60,
    'HOUR': 3600,
    'DAY': 84400
}



def _get_root_helper():
    return 'sudo xdrs-rootwrap %s' % CONF.rootwrap_config


def execute(*cmd, **kwargs):
    """Convenience wrapper around oslo's execute() method."""
    if 'run_as_root' in kwargs and not 'root_helper' in kwargs:
        kwargs['root_helper'] = _get_root_helper()
    return processutils.execute(*cmd, **kwargs)


def xdrsdir():
    return os.path.abspath(xdrs.__file__).split('xdrs/__init__.py')[0]


def generate_uid(topic, size=8):
    characters = '01234567890abcdefghijklmnopqrstuvwxyz'
    choices = [random.choice(characters) for _x in xrange(size)]
    return '%s-%s' % (topic, ''.join(choices))


# Default symbols to use for passwords. Avoids visually confusing characters.
# ~6 bits per symbol
DEFAULT_PASSWORD_SYMBOLS = ('23456789',  # Removed: 0,1
                            'ABCDEFGHJKLMNPQRSTUVWXYZ',   # Removed: I, O
                            'abcdefghijkmnopqrstuvwxyz')  # Removed: l


# ~5 bits per symbol
EASIER_PASSWORD_SYMBOLS = ('23456789',  # Removed: 0, 1
                           'ABCDEFGHJKLMNPQRSTUVWXYZ')  # Removed: I, O


def utf8(value):
    """
    Try to turn a string into utf-8 if possible.
    """
    if isinstance(value, unicode):
        return value.encode('utf-8')
    elif isinstance(value, gettextutils.Message):
        return unicode(value).encode('utf-8')
    assert isinstance(value, str)
    return value


"""
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
"""
def check_isinstance(obj, cls):
    """Checks that obj is of type cls, and lets PyLint infer types."""
    if isinstance(obj, cls):
        return obj
    raise Exception(_('Expected object of type: %s') % (str(cls)))


def monkey_patch():
    # If CONF.monkey_patch is not True, this function do nothing.
    if not CONF.monkey_patch:
        return
    # Get list of modules and decorators
    for module_and_decorator in CONF.monkey_patch_modules:
        module, decorator_name = module_and_decorator.split(':')
        # import decorator function
        decorator = importutils.import_class(decorator_name)
        __import__(module)
        # Retrieve module information using pyclbr
        module_data = pyclbr.readmodule_ex(module)
        for key in module_data.keys():
            # set the decorator for the class methods
            if isinstance(module_data[key], pyclbr.Class):
                clz = importutils.import_class("%s.%s" % (module, key))
                for method, func in inspect.getmembers(clz, inspect.ismethod):
                    setattr(clz, method,
                        decorator("%s.%s.%s" % (module, key, method), func))
            # set the decorator for the function
            if isinstance(module_data[key], pyclbr.Function):
                func = importutils.import_class("%s.%s" % (module, key))
                setattr(sys.modules[module], key,
                    decorator("%s.%s" % (module, key), func))


def read_cached_file(filename, cache_info, reload_func=None):
    """
    Read from a file if it has been modified.
    """
    mtime = os.path.getmtime(filename)
    if not cache_info or mtime != cache_info.get('mtime'):
        LOG.debug(_("Reloading cached file %s") % filename)
        with open(filename) as fap:
            cache_info['data'] = fap.read()
        cache_info['mtime'] = mtime
        if reload_func:
            reload_func(cache_info['data'])
    return cache_info['data']



def chown(path, owner_uid=None):
    """
    改变路径的访问和操作权限；
    """
    if owner_uid is None:
        owner_uid = os.getuid()

    orig_uid = os.stat(path).st_uid

    if orig_uid != owner_uid:
        execute('chown', owner_uid, path, run_as_root=True)


@contextlib.contextmanager
def tempdir(**kwargs):
    argdict = kwargs.copy()
    if 'dir' not in argdict:
        argdict['dir'] = CONF.tempdir
    tmpdir = tempfile.mkdtemp(**argdict)
    try:
        yield tmpdir
    finally:
        try:
            shutil.rmtree(tmpdir)
        except OSError as e:
            LOG.error(_('Could not remove tmpdir: %s'), str(e))


def walk_class_hierarchy(clazz, encountered=None):
    """
    Walk class hierarchy, yielding most derived classes first.
    """
    if not encountered:
        encountered = []
    for subclass in clazz.__subclasses__():
        if subclass not in encountered:
            encountered.append(subclass)
            # drill down to leaves first
            for subsubclass in walk_class_hierarchy(subclass, encountered):
                yield subsubclass
            yield subclass


def metadata_to_dict(metadata):
    result = {}
    for item in metadata:
        if not item.get('deleted'):
            result[item['key']] = item['value']
    return result


def get_wrapped_function(function):
    """Get the method at the bottom of a stack of decorators."""
    if not hasattr(function, 'func_closure') or not function.func_closure:
        return function

    def _get_wrapped_function(function):
        if not hasattr(function, 'func_closure') or not function.func_closure:
            return None

        for closure in function.func_closure:
            func = closure.cell_contents

            deeper_func = _get_wrapped_function(func)
            if deeper_func:
                return deeper_func
            elif hasattr(closure.cell_contents, '__call__'):
                return closure.cell_contents

    return _get_wrapped_function(function)


class ExceptionHelper(object):
    """Class to wrap another and translate the ClientExceptions raised by its
    function calls to the actual ones.
    """

    def __init__(self, target):
        self._target = target

    def __getattr__(self, name):
        func = getattr(self._target, name)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except messaging.ExpectedException as e:
                raise (e.exc_info[1], None, e.exc_info[2])
        return wrapper


def check_string_length(value, name, min_length=0, max_length=None):
    """
    Check the length of specified string
    检测指定字符串的长度；
    """
    if not isinstance(value, six.string_types):
        msg = _("%s is not a string or unicode") % name
        raise exception.InvalidInput(message=msg)

    if len(value) < min_length:
        msg = _("%(name)s has a minimum character requirement of "
                "%(min_length)s.") % {'name': name, 'min_length': min_length}
        raise exception.InvalidInput(message=msg)

    if max_length and len(value) > max_length:
        msg = _("%(name)s has more than %(max_length)s "
                "characters.") % {'name': name, 'max_length': max_length}
        raise exception.InvalidInput(message=msg)


def validate_integer(value, name, min_value=None, max_value=None):
    """
    Make sure that value is a valid integer, potentially within range.
    """
    try:
        value = int(str(value))
    except (ValueError, UnicodeEncodeError):
        msg = _('%(value_name)s must be an integer')
        raise exception.InvalidInput(reason=(
            msg % {'value_name': name}))

    if min_value is not None:
        if value < min_value:
            msg = _('%(value_name)s must be >= %(min_value)d')
            raise exception.InvalidInput(
                reason=(msg % {'value_name': name,
                               'min_value': min_value}))
    if max_value is not None:
        if value > max_value:
            msg = _('%(value_name)s must be <= %(max_value)d')
            raise exception.InvalidInput(
                reason=(
                    msg % {'value_name': name,
                           'max_value': max_value})
            )
    return value


def spawn_n(func, *args, **kwargs):
    """
    Passthrough method for eventlet.spawn_n.
    This utility exists so that it can be stubbed for testing without
    interfering with the service spawns.
    """
    eventlet.spawn_n(func, *args, **kwargs)


def is_none_string(val):
    """
    Check if a string represents a None value.
    """
    if not isinstance(val, six.string_types):
        return False

    return val.lower() == 'none'



def get_hash_str(base_str):
    """
    returns string that represents hash of base_str (in hex format).
    """
    return hashlib.md5(base_str).hexdigest()


def cpu_count():
    try:
        return multiprocessing.cpu_count()
    except NotImplementedError:
        return 1

if hasattr(hmac, 'compare_digest'):
    constant_time_compare = hmac.compare_digest
else:
    def constant_time_compare(first, second):
        """
        Returns True if both string inputs are equal, otherwise False.
        This function should take a constant amount of time regardless of
        how many characters in the strings match.
        """
        if len(first) != len(second):
            return False
        result = 0
        for x, y in zip(first, second):
            result |= ord(x) ^ ord(y)
        return result == 0


def drop_privileges(user):
    """
    Sets the userid/groupid of the current process, get session leader, etc.
    """
    if os.geteuid() == 0:
        groups = [g.gr_gid for g in grp.getgrall() if user in g.gr_mem]
        os.setgroups(groups)
    user = pwd.getpwnam(user)
    os.setgid(user[3])
    os.setuid(user[2])
    os.environ['HOME'] = user[5]
    try:
        os.setsid()
    except OSError:
        pass
    os.chdir('/')   # in case you need to rmdir on where you started the daemon
    os.umask(0o22)  # ensure files are created with the correct privileges


def mkdirs(path):
    """
    Ensures the path is a directory or makes it if not. Errors if the path
    exists but is a file or on permissions failure.
    路径的建立操作；
    """
    if not os.path.isdir(path):
        try:
            os.makedirs(path)
        except OSError as err:
            if err.errno != errno.EEXIST or not os.path.isdir(path):
                raise


def renamer(old, new):
    """
    Attempt to fix / hide race conditions like empty object directories
    being removed by backend processes during uploads, by retrying.
    文件的重命名操作；
    """
    try:
        mkdirs(os.path.dirname(new))
        os.rename(old, new)
    except OSError:
        mkdirs(os.path.dirname(new))
        os.rename(old, new)


def parse_options(parser=None, once=False, test_args=None):
    """
    Parse standard swift server/daemon options with optparse.OptionParser.
    """
    if not parser:
        parser = OptionParser(usage="%prog CONFIG [options]")
    parser.add_option("-v", "--verbose", default=False, action="store_true",
                      help="log to console")
    if once:
        parser.add_option("-o", "--once", default=False, action="store_true",
                          help="only run one pass of daemon")

    # if test_args is None, optparse will use sys.argv[:1]
    options, args = parser.parse_args(args=test_args)

    if not args:
        parser.print_usage()
        print _("Error: missing config path argument")
        sys.exit(1)
    config = os.path.abspath(args.pop(0))
    if not os.path.exists(config):
        parser.print_usage()
        print _("Error: unable to locate %s") % config
        sys.exit(1)

    extra_args = []
    # if any named options appear in remaining args, set the option to True
    for arg in args:
        if arg in options.__dict__:
            setattr(options, arg, True)
        else:
            extra_args.append(arg)

    options = vars(options)
    if extra_args:
        options['extra_args'] = extra_args
    return config, options


def lock_path(directory, timeout=10, timeout_class=None):
    """
    Context manager that acquires a lock on a directory.  
    This will block until
    the lock can be acquired, or the timeout time has expired (whichever occurs
    first).
    """
    if timeout_class is None:
        timeout_class = xdrs.exception.LockTimeout
    mkdirs(directory)
    lockpath = '%s/.lock' % directory
    fd = os.open(lockpath, os.O_WRONLY | os.O_CREAT)
    try:
        with timeout_class(timeout, lockpath):
            while True:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except IOError as err:
                    if err.errno != errno.EAGAIN:
                        raise
                sleep(0.01)
        yield True
    finally:
        os.close(fd)


"""
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
"""
def lock_file(filename, timeout=10, append=False, unlink=True):
    """
    Context manager that acquires a lock on a file.  This will block until
    the lock can be acquired, or the timeout time has expired (whichever occurs
    first).

    :param filename: file to be locked
    :param timeout: timeout (in seconds)
    :param append: True if file should be opened in append mode
    :param unlink: True if the file should be unlinked at the end
    """
    flags = os.O_CREAT | os.O_RDWR
    if append:
        flags |= os.O_APPEND
        mode = 'a+'
    else:
        mode = 'r+'
    fd = os.open(filename, flags)
    file_obj = os.fdopen(fd, mode)
    try:
        with xdrs.exception.LockTimeout(timeout, filename):
            while True:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except IOError as err:
                    if err.errno != errno.EAGAIN:
                        raise
                sleep(0.01)
        yield file_obj
    finally:
        try:
            file_obj.close()
        except UnboundLocalError:
            pass  # may have not actually opened the file
        if unlink:
            os.unlink(filename)


def get_time_units(time_amount):
    """
    Get a nomralized length of time in the largest unit of time (hours,
    minutes, or seconds.)
    获取时间信息；
    """
    time_unit = 's'
    if time_amount > 60:
        time_amount /= 60
        time_unit = 'm'
        if time_amount > 60:
            time_amount /= 60
            time_unit = 'h'
    return time_amount, time_unit


def remove_file(path):
    """
    Quiet wrapper for os.unlink, OSErrors are suppressed
    删除指定的文件；
    """
    try:
        os.unlink(path)
    except OSError:
        pass


class GreenAsyncPileWaitallTimeout(Timeout):
    pass


class ModifiedParseResult(ParseResult):
    "Parse results class for urlparse."

    @property
    def hostname(self):
        netloc = self.netloc.split('@', 1)[-1]
        if netloc.startswith('['):
            return netloc[1:].split(']')[0]
        elif ':' in netloc:
            return netloc.rsplit(':')[0]
        return netloc

    @property
    def port(self):
        netloc = self.netloc.split('@', 1)[-1]
        if netloc.startswith('['):
            netloc = netloc.rsplit(']')[1]
        if ':' in netloc:
            return int(netloc.rsplit(':')[1])
        return None


def urlparse(url):
    """
    urlparse augmentation.
    This is necessary because urlparse can't handle RFC 2732 URLs.
    """
    return ModifiedParseResult(*stdlib_urlparse(url))



def get_remote_client(req):
    client = req.headers.get('x-cluster-client-ip')
    if not client and 'x-forwarded-for' in req.headers:
        # remote host for other lbs
        client = req.headers['x-forwarded-for'].split(',')[0].strip()
    if not client:
        client = req.remote_addr
    return client



def listdir(path):
    try:
        return os.listdir(path)
    except OSError as err:
        if err.errno != errno.ENOENT:
            raise
    return []



def public(func):
    """
    Decorator to declare which methods are publicly accessible as HTTP
    requests
    """
    func.publicly_accessible = True

    @functools.wraps(func)
    def wrapped(*a, **kw):
        return func(*a, **kw)
    return wrapped


class CloseableChain(object):
    """
    Like itertools.chain, but with a close method that will attempt to invoke
    its sub-iterators' close methods, if any.
    """
    def __init__(self, *iterables):
        self.iterables = iterables

    def __iter__(self):
        return iter(itertools.chain(*(self.iterables)))

    def close(self):
        for it in self.iterables:
            close_method = getattr(it, 'close', None)
            if close_method:
                close_method()