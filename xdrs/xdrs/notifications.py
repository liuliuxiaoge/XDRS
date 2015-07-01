"""
Functionality related to notifications common to multiple layers of
the system.
"""

from oslo.config import cfg

from xdrs.openstack.common import context as common_context
from xdrs.openstack.common import log
from xdrs import rpc

LOG = log.getLogger(__name__)

CONF = cfg.CONF
CONF.import_opt('default_publisher_id', 'xdrs.service')
CONF.import_opt('default_notification_level', 'xdrs.service')
CONF.import_opt('notify_api_faults', 'xdrs.service')

def notify_decorator(name, fn):
    """
    Decorator for notify which is used from utils.monkey_patch().
    """
    def wrapped_func(*args, **kwarg):
        body = {}
        body['args'] = []
        body['kwarg'] = {}
        for arg in args:
            body['args'].append(arg)
        for key in kwarg:
            body['kwarg'][key] = kwarg[key]

        ctxt = common_context.get_context_from_function_and_args(
            fn, args, kwarg)

        notifier = rpc.get_notifier(publisher_id=(CONF.default_publisher_id
                                                  or CONF.host))
        method = notifier.getattr(CONF.default_notification_level.lower(),
                                  'info')
        method(ctxt, name, body)

        return fn(*args, **kwarg)
    return wrapped_func


def send_api_fault(url, status, exception):
    """
    Send an api.fault notification.
    """

    if not CONF.notify_api_faults:
        return

    payload = {'url': url, 'exception': str(exception), 'status': status}

    rpc.get_notifier('api').error(None, 'api.fault', payload)