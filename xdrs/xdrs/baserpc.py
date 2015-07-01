"""
Base RPC client and server common to all services.
RPC的服务端和客户端的基类；
"""

from oslo.config import cfg
from oslo import messaging

from xdrs.openstack.common import jsonutils
from xdrs import rpc


CONF = cfg.CONF
rpcapi_cap_opt = cfg.StrOpt('baseapi',
        help='Set a version cap for messages sent to the base api in any '
             'service')
CONF.register_opt(rpcapi_cap_opt, 'upgrade_levels')

_NAMESPACE = 'baseapi'



class BaseAPI(object):
    """
    Client side of the base rpc API.
    """

    VERSION_ALIASES = {
    }

    def __init__(self, topic):
        super(BaseAPI, self).__init__()
        target = messaging.Target(topic=topic,
                                  namespace=_NAMESPACE,
                                  version='1.0')
        version_cap = self.VERSION_ALIASES.get(CONF.upgrade_levels.baseapi,
                                               CONF.upgrade_levels.baseapi)
        self.client = rpc.get_client(target, version_cap=version_cap)

    def ping(self, context, arg, timeout=None):
        arg_p = jsonutils.to_primitive(arg)
        cctxt = self.client.prepare(timeout=timeout)
        return cctxt.call(context, 'ping', arg=arg_p)

    def get_backdoor_port(self, context, host):
        cctxt = self.client.prepare(server=host, version='1.1')
        return cctxt.call(context, 'get_backdoor_port')


class BaseRPCAPI(object):
    """
    Server side of the base RPC API.
    """

    target = messaging.Target(namespace=_NAMESPACE, version='1.1')

    def __init__(self, service_name, backdoor_port):
        self.service_name = service_name
        self.backdoor_port = backdoor_port

    def ping(self, context, arg):
        resp = {'service': self.service_name, 'arg': arg}
        return jsonutils.to_primitive(resp)

    def get_backdoor_port(self, context):
        return self.backdoor_port