'''
JSON related utilities.

This module provides a few things:

    1) A handy function for getting an object down to something that can be
    JSON serialized.  See to_primitive().

    2) Wrappers around loads() and dumps().  The dumps() wrapper will
    automatically use to_primitive() for you if needed.

    3) This sets up anyjson to use the loads() and dumps() wrappers if anyjson
    is available.
'''

import datetime
import functools
import inspect
import itertools
import json
try:
    import xmlrpclib
except ImportError:
    # NOTE(jd): xmlrpclib is not shipped with Python 3
    xmlrpclib = None

import six

from xdrs.openstack.common import gettextutils
from xdrs.openstack.common import importutils
from xdrs.openstack.common import timeutils

netaddr = importutils.try_import("netaddr")

_nasty_type_tests = [inspect.ismodule, inspect.isclass, inspect.ismethod,
                     inspect.isfunction, inspect.isgeneratorfunction,
                     inspect.isgenerator, inspect.istraceback, inspect.isframe,
                     inspect.iscode, inspect.isbuiltin, inspect.isroutine,
                     inspect.isabstract]

_simple_types = (six.string_types + six.integer_types
                 + (type(None), bool, float))


def to_primitive(value, convert_instances=False, convert_datetime=True,
                 level=0, max_depth=3):
    if isinstance(value, _simple_types):
        return value

    if isinstance(value, datetime.datetime):
        if convert_datetime:
            return timeutils.strtime(value)
        else:
            return value

    # value of itertools.count doesn't get caught by nasty_type_tests
    # and results in infinite loop when list(value) is called.
    if type(value) == itertools.count:
        return six.text_type(value)

    # FIXME(vish): Workaround for LP bug 852095. Without this workaround,
    #              tests that raise an exception in a mocked method that
    #              has a @wrap_exception with a notifier will fail. If
    #              we up the dependency to 0.5.4 (when it is released) we
    #              can remove this workaround.
    if getattr(value, '__module__', None) == 'mox':
        return 'mock'

    if level > max_depth:
        return '?'

    # The try block may not be necessary after the class check above,
    # but just in case ...
    try:
        recursive = functools.partial(to_primitive,
                                      convert_instances=convert_instances,
                                      convert_datetime=convert_datetime,
                                      level=level,
                                      max_depth=max_depth)
        if isinstance(value, dict):
            return dict((k, recursive(v)) for k, v in six.iteritems(value))
        elif isinstance(value, (list, tuple)):
            return [recursive(lv) for lv in value]

        # It's not clear why xmlrpclib created their own DateTime type, but
        # for our purposes, make it a datetime type which is explicitly
        # handled
        if xmlrpclib and isinstance(value, xmlrpclib.DateTime):
            value = datetime.datetime(*tuple(value.timetuple())[:6])

        if convert_datetime and isinstance(value, datetime.datetime):
            return timeutils.strtime(value)
        elif isinstance(value, gettextutils.Message):
            return value.data
        elif hasattr(value, 'iteritems'):
            return recursive(dict(value.iteritems()), level=level + 1)
        elif hasattr(value, '__iter__'):
            return recursive(list(value))
        elif convert_instances and hasattr(value, '__dict__'):
            # Likely an instance of something. Watch for cycles.
            # Ignore class member vars.
            return recursive(value.__dict__, level=level + 1)
        elif netaddr and isinstance(value, netaddr.IPAddress):
            return six.text_type(value)
        else:
            if any(test(value) for test in _nasty_type_tests):
                return six.text_type(value)
            return value
    except TypeError:
        # Class objects are tricky since they may define something like
        # __iter__ defined but it isn't callable as list().
        return six.text_type(value)


def dumps(value, default=to_primitive, **kwargs):
    return json.dumps(value, default=default, **kwargs)


def loads(s):
    return json.loads(s)


def load(s):
    return json.load(s)


try:
    import anyjson
except ImportError:
    pass
else:
    anyjson._modules.append((__name__, 'dumps', TypeError,
                                       'loads', ValueError, 'load'))
    anyjson.force_implementation(__name__)