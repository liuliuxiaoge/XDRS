"""
暂时只应用到方法：
def set_defaults(control_exchange)
def init(conf)
def get_allowed_exmods()
TRANSPORT_ALIASES（只保留AMQP的一种实现方式RabbitMQ，相应的实现文件也要作调整；）
其他方法是否需要应用，待一步步确定；
若干跟nova相关的参数如何修改，待一步步确定；
注意检查所使用方法的输入输出，保证完全的（从nova的）修改；
"""

__all__ = [
    'init',
    'cleanup',
    'set_defaults',
    'add_extra_exmods',
    'clear_extra_exmods',
    'get_allowed_exmods',
    'RequestContextSerializer',
    'get_client',
    'get_server',
    'get_notifier',
    'TRANSPORT_ALIASES',
]

from oslo.config import cfg
from oslo import messaging

import xdrs.exception
from xdrs.openstack.common import jsonutils

CONF = cfg.CONF

TRANSPORT = None
NOTIFIER = None

ALLOWED_EXMODS = [
    xdrs.exception.__name__,
]
EXTRA_EXMODS = []

"""
注：只保留AMQP的一种实现方式RabbitMQ；
"""
TRANSPORT_ALIASES = {
    'nova.openstack.common.rpc.impl_kombu': 'rabbit',
    'nova.rpc.impl_kombu': 'rabbit',
}


def init(conf):
    """
    初始化过程，实现三方面内容的初始化：
    1.确定xdrs异常类的基类的处理文件xdrs.exception；
    2.确定了使用rabbit这个AMQP的driver方式:
    3.加载notifier各种驱动实现方式：
      [oslo.messaging.notify.drivers]
      log = oslo.messaging.notify._impl_log:LogDriver
      messagingv2 = oslo.messaging.notify._impl_messaging:MessagingV2Driver
      noop = oslo.messaging.notify._impl_noop:NoOpDriver
      routing = oslo.messaging.notify._impl_routing:RoutingDriver
      test = oslo.messaging.notify._impl_test:TestDriver
      messaging = oslo.messaging.notify._impl_messaging:MessagingDriver
    """
    global TRANSPORT, NOTIFIER
    exmods = get_allowed_exmods()
    """
    exmods = ['xdrs.exception']
    这个方法实现了确定xdrs异常类的基类的处理文件；
    """
    
    TRANSPORT = messaging.get_transport(conf,
                                        allowed_remote_exmods=exmods,
                                        aliases=TRANSPORT_ALIASES)
    """
    ======================================================================================
    conf = <oslo.config.cfg.ConfigOpts object at 0x1ebf490>
    allowed_remote_exmods = ['xdrs.exception']
    aliases = {
              'nova.openstack.common.rpc.impl_kombu': 'rabbit'
              'nova.rpc.impl_kombu': 'rabbit', 
              }
    TRANSPORT = <oslo.messaging.transport.Transport object at 0x30b5150>
    ======================================================================================
    ======================================================================================
    返回值复制给TRANSPORT，实际上这里实现的就是确定了使用rabbit这个driver:
    mgr = <stevedore.driver.DriverManager object at 0x2d5a090>
    mgr.driver = <oslo.messaging._drivers.impl_rabbit.RabbitDriver object at 0x2dd90d0>
    Transport(mgr.driver) = <oslo.messaging.transport.Transport object at 0x311f210>
    TRANSPORT._driver = <oslo.messaging._drivers.impl_rabbit.RabbitDriver object at 0x3a000d0>
    ======================================================================================
    """
    serializer = RequestContextSerializer(JsonPayloadSerializer())
    """
    这里实现的是加载notifier各种驱动实现方式；
    [oslo.messaging.notify.drivers]
    log = oslo.messaging.notify._impl_log:LogDriver
    messagingv2 = oslo.messaging.notify._impl_messaging:MessagingV2Driver
    noop = oslo.messaging.notify._impl_noop:NoOpDriver
    routing = oslo.messaging.notify._impl_routing:RoutingDriver
    test = oslo.messaging.notify._impl_test:TestDriver
    messaging = oslo.messaging.notify._impl_messaging:MessagingDriver
    """
    NOTIFIER = messaging.Notifier(TRANSPORT, serializer=serializer)


def cleanup():
    global TRANSPORT, NOTIFIER
    assert TRANSPORT is not None
    assert NOTIFIER is not None
    TRANSPORT.cleanup()
    TRANSPORT = NOTIFIER = None


def set_defaults(control_exchange):
    messaging.set_transport_defaults(control_exchange)
    """
    def set_transport_defaults(control_exchange):
        cfg.set_defaults(_transport_opts,
                     control_exchange=control_exchange)
    ======================================================================================
    _transport_opts = [<oslo.config.cfg.StrOpt object at 0x21f45d0>, 
                      <oslo.config.cfg.StrOpt object at 0x220f150>, 
                      <oslo.config.cfg.StrOpt object at 0x220f890>]
    control_exchange = xdrs
    ======================================================================================
    
    _transport_opts = [
    cfg.StrOpt('transport_url',
               default=None,
               help='A URL representing the messaging driver to use and its '
                    'full configuration. If not set, we fall back to the '
                    'rpc_backend option and driver specific configuration.'),
    cfg.StrOpt('rpc_backend',
               default='rabbit',
               help='The messaging driver to use, defaults to rabbit. Other '
                    'drivers include qpid and zmq.'),
    cfg.StrOpt('control_exchange',
               default='openstack',
               help='The default exchange under which topics are scoped. May '
                    'be overridden by an exchange name specified in the '
                    'transport_url option.'),
    ]
    
    可见这个方法实现的就是RPC若干参数选项默认值的设置和注册，包括：
    transport_url（default=None），
    rpc_backend（default='rabbit'）
    control_exchange（default='openstack'）；
    同时指定了control_exchange = xdrs作为参数选项的默认值，所以：
    control_exchange（default='xdrs'）；
    """


def add_extra_exmods(*args):
    EXTRA_EXMODS.extend(args)


def clear_extra_exmods():
    del EXTRA_EXMODS[:]


def get_allowed_exmods():
    """
    注：这个方法实现了确定xdrs异常类的基类的处理文件；
    ======================================================================================
    ALLOWED_EXMODS = ['xdrs.exception']
    EXTRA_EXMODS = []
    ALLOWED_EXMODS + EXTRA_EXMODS = ['xdrs.exception']
    ======================================================================================
    """
    return ALLOWED_EXMODS + EXTRA_EXMODS


class JsonPayloadSerializer(messaging.NoOpSerializer):
    @staticmethod
    def serialize_entity(context, entity):
        return jsonutils.to_primitive(entity, convert_instances=True)


class RequestContextSerializer(messaging.Serializer):

    def __init__(self, base):
        self._base = base

    def serialize_entity(self, context, entity):
        if not self._base:
            return entity
        return self._base.serialize_entity(context, entity)

    def deserialize_entity(self, context, entity):
        if not self._base:
            return entity
        return self._base.deserialize_entity(context, entity)

    def serialize_context(self, context):
        return context.to_dict()

    def deserialize_context(self, context):
        return xdrs.context.RequestContext.from_dict(context)


def get_transport_url(url_str=None):
    return messaging.TransportURL.parse(CONF, url_str, TRANSPORT_ALIASES)


def get_client(target, version_cap=None, serializer=None):
    assert TRANSPORT is not None
    serializer = RequestContextSerializer(serializer)
    return messaging.RPCClient(TRANSPORT,
                               target,
                               version_cap=version_cap,
                               serializer=serializer)

def get_server(target, endpoints, serializer=None):
    assert TRANSPORT is not None
    serializer = RequestContextSerializer(serializer)
    return messaging.get_rpc_server(TRANSPORT,
                                    target,
                                    endpoints,
                                    executor='eventlet',
                                    serializer=serializer)


def get_notifier(service=None, host=None, publisher_id=None):
    assert NOTIFIER is not None
    if not publisher_id:
        publisher_id = "%s.%s" % (service, host or CONF.host)
    return NOTIFIER.prepare(publisher_id=publisher_id)