"""
Xdrs项目中的异常处理；
"""

import functools
import sys

from oslo.config import cfg
import webob.exc
from eventlet import Timeout

from xdrs.openstack.common import excutils
from xdrs.openstack.common.gettextutils import _
from xdrs.openstack.common import log as logging
from xdrs import safe_utils

LOG = logging.getLogger(__name__)

CONF = cfg.CONF
CONF.import_opt('fatal_exception_format_errors', 'xdrs.service')

class ConvertedException(webob.exc.WSGIHTTPException):
    def __init__(self, code=0, title="", explanation=""):
        self.code = code
        self.title = title
        self.explanation = explanation
        super(ConvertedException, self).__init__()

class MessageTimeout(Timeout):

    def __init__(self, seconds=None, msg=None):
        Timeout.__init__(self, seconds=seconds)
        self.msg = msg

    def __str__(self):
        return '%s: %s' % (Timeout.__str__(self), self.msg)


def _cleanse_dict(original):
    """Strip all admin_password, new_pass, rescue_pass keys from a dict."""
    return dict((k, v) for k, v in original.iteritems() if not "_pass" in k)


def wrap_exception(notifier=None, get_notifier=None):
    """T
    his decorator wraps a method to catch any exceptions that may
    get thrown. It logs the exception as well as optionally sending
    it to the notification system.
    """
    def inner(f):
        def wrapped(self, context, *args, **kw):
            # Don't store self or context in the payload, it now seems to
            # contain confidential information.
            try:
                return f(self, context, *args, **kw)
            except Exception as e:
                with excutils.save_and_reraise_exception():
                    if notifier or get_notifier:
                        payload = dict(exception=e)
                        call_dict = safe_utils.getcallargs(f, context,
                                                           *args, **kw)
                        cleansed = _cleanse_dict(call_dict)
                        payload.update({'args': cleansed})

                        # If f has multiple decorators, they must use
                        # functools.wraps to ensure the name is
                        # propagated.
                        event_type = f.__name__

                        (notifier or get_notifier()).error(context,
                                                           event_type,
                                                           payload)

        return functools.wraps(f)(wrapped)
    return inner


class XdrsException(Exception):
    """
    Xdrs的异常处理类；
    """
    msg_fmt = _("An unknown exception occurred.")
    code = 500
    headers = {}
    safe = False

    def __init__(self, message=None, **kwargs):
        self.kwargs = kwargs

        if 'code' not in self.kwargs:
            try:
                self.kwargs['code'] = self.code
            except AttributeError:
                pass

        if not message:
            try:
                message = self.msg_fmt % kwargs

            except Exception:
                exc_info = sys.exc_info()
                # kwargs doesn't match a variable in the message
                # log the issue and the kwargs
                LOG.exception(_('Exception in string format operation'))
                for name, value in kwargs.iteritems():
                    LOG.error("%s: %s" % (name, value))

                if CONF.fatal_exception_format_errors:
                    raise exc_info[0], exc_info[1], exc_info[2]
                else:
                    # at least get the core message out if something happened
                    message = self.msg_fmt

        super(XdrsException, self).__init__(message)

    def format_message(self):
        return self.args[0]


class NotAuthorized(XdrsException):
    ec2_code = 'AuthFailure'
    msg_fmt = _("Not authorized.")
    code = 403


class AdminRequired(NotAuthorized):
    msg_fmt = _("User does not have admin privileges")


class PolicyNotAuthorized(NotAuthorized):
    msg_fmt = _("Policy doesn't allow %(action)s to be performed.")


class Invalid(XdrsException):
    msg_fmt = _("Unacceptable parameters.")
    code = 400


class ValidationError(Invalid):
    msg_fmt = "%(detail)s"


class InvalidInput(Invalid):
    msg_fmt = _("Invalid input received: %(reason)s")
    

class InstanceInvalidState(Invalid):
    msg_fmt = _("Instance %(instance_uuid)s in %(attr)s %(state)s. Cannot "
                "%(method)s while the instance is in this state.")

class InstanceNotReady(Invalid):
    msg_fmt = _("Instance %(instance_id)s is not ready")


class NotFound(XdrsException):
    msg_fmt = _("Resource could not be found.")
    code = 404


class ServiceNotFound(NotFound):
    msg_fmt = _("Service %(service_id)s could not be found.")


class ServiceBinaryExists(XdrsException):
    msg_fmt = _("Service with host %(host)s binary %(binary)s exists.")


class ServiceTopicExists(XdrsException):
    msg_fmt = _("Service with host %(host)s topic %(topic)s exists.")


class HostNotFound(NotFound):
    msg_fmt = _("Host %(host)s could not be found.")


class FileNotFound(NotFound):
    msg_fmt = _("File %(file_path)s could not be found.")


class NoFilesFound(NotFound):
    msg_fmt = _("Zero files could be found.")

class ClassNotFound(NotFound):
    msg_fmt = _("Class %(class_name)s could not be found: %(exception)s")


class NotAllowed(XdrsException):
    msg_fmt = _("Action not allowed.")


class MalformedRequestBody(XdrsException):
    msg_fmt = _("Malformed message body: %(reason)s")


class ConfigNotFound(XdrsException):
    msg_fmt = _("Could not find config at %(path)s")


class PasteAppNotFound(XdrsException):
    msg_fmt = _("Could not load paste app '%(name)s' from %(path)s")


class NodeNotFound(NotFound):
    msg_fmt = _("Node %(node_id)s could not be found.")


class NodeNotFoundByUUID(NotFound):
    msg_fmt = _("Node with UUID %(node_uuid)s could not be found.")


class InstanceIsLocked(InstanceInvalidState):
    msg_fmt = _("Instance %(instance_uuid)s is locked")


class UnsupportedObjectError(XdrsException):
    msg_fmt = _('Unsupported object type %(objtype)s')


class IncompatibleObjectVersion(XdrsException):
    msg_fmt = _('Version %(objver)s of %(objname)s is not supported')


class LocalVmMetadataNotFound(Invalid):
    msg_fmt = _("The local vm metadata not found.")
    
class LocalHostNotFound(Invalid):
    msg_fmt = _("The local host not found.")

class DataCollectorInitNotFound(Invalid):
    msg_fmt = _("The data collector init not found.")

class VmCpuDataNotFound(Invalid):
    msg_fmt = _("The vm cpu data init not found.")

class HostCpuDataNotFound(Invalid):
    msg_fmt = _("The host cpu data init not found.")

class HostMemroyInfoNotFound(Invalid):
    msg_fmt = _("host memroy info not found.")
    
class VmsOnHostRamNotFoune(Invalid):
    msg_fmt = _("vms on specific host ram data not found.")
    
class AlgorithmsNotFound(NotFound):
    msg_fmt = _("Algorithms could not be found.")
    
class UnderloadAlgorithmsNotFound(NotFound):
    msg_fmt = _("Underload algorithms could not be found.")
    
class OverloadAlgorithmsNotFound(NotFound):
    msg_fmt = _("Overload algorithms could not be found.")
    
class FilterSchedulerAlgorithmsNotFound(NotFound):
    msg_fmt = _("Filter scheduler algorithms could not be found.")
    
class HostSchedulerAlgorithmsNotFound(NotFound):
    msg_fmt = _("Host scheduler algorithms could not be found.")
    
class UnderloadAlgorithmNotFound(Invalid):
    msg_fmt = _("Underload algorithms could not be found.")
    
class OverloadAlgorithmNotFound(Invalid):
    msg_fmt = _("Overload algorithms could not be found.")
    
class FilterSchedulerAlgorithmNotFound(Invalid):
    msg_fmt = _("Filter scheduler algorithms could not be found.")
    
class HostSchedulerAlgorithmNotFound(Invalid):
    msg_fmt = _("Host scheduler algorithms could not be found.")

class VmSelectAlgorithmNotFound(Invalid):
    msg_fmt = _("Vm select algorithms could not be found.")
    
class AlgorithmNotFound(NotFound):
    msg_fmt = _("Algorithms could not be found.")
    
class HostStateNotFound(NotFound):
    msg_fmt = _("Hosts States could not be found.")
    
class HostTaskStateNotFound(NotFound):
    msg_fmt = _("Hosts Task States could not be found.")
    
class HostRunningStateNotFound(NotFound):
    msg_fmt = _("Hosts Running States could not be found.")
    
class HostLoadStateNotFound(NotFound):
    msg_fmt = _("Hosts Load States could not be found.")
    
class VmMetadataNotFound(Invalid):
    msg_fmt = _("The vm metadata init not found.")
    
class VmMigrationRecordNotFound(Invalid):
    msg_fmt = _("The vm migration record not found.")
    
class HostMigrationRecordNotFound(Invalid):
    msg_fmt = _("The Host migration record not found.")
    
class HostInitDataNotFound(NotFound):
    msg_fmt = _("Host Init Data could not be found.")
    
class XdrsControllerError():
    msg_fmt = _("There are some error in DRS operation.")
    
class DataCollectionError():
    msg_fmt = _("There are some error in DRS hosts and vms data collection operation.")

class LoadDetectionError():
    msg_fmt = _("There are some error in hosts load detection operation.")

class VmsSelectionError():
    msg_fmt = _("There are some error in vms selection operation.")

class LockTimeout(MessageTimeout):
    pass