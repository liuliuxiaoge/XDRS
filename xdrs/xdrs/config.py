"""
这里使用了方法：
def parse_args(argv, default_config_files=None)
需要对其进行进一步的检查修正；
"""

from oslo.config import cfg

from xdrs import debugger
from xdrs.openstack.common.db import options
from xdrs import paths
from xdrs import rpc
from xdrs import version

_DEFAULT_SQL_CONNECTION = 'sqlite:///' + paths.state_path_def('xdrs.sqlite')


def parse_args(argv, default_config_files=None):
    """
    方法parse_args主要实现了以下功能：
    1.实现设置注册数据库的默认参数选项值，其默认的参数选项值如database_opts所设置；
    2.实现RPC若干参数选项默认值的设置和注册，包括：
      transport_url（default=None），
      rpc_backend（default='rabbit'）
      control_exchange（default='xdrs'）；
    3.实现确定xdrs-api所应用配置文件路径：
      default_config_files = ['/usr/share/xdrs/xdrs-dist.conf', 
                            '/etc/xdrs/xdrs.conf']
      实现注册配置文件路径等参数选项到系统；
    4.确定xdrs异常类的基类的处理文件xdrs.exception；
      确定了使用rabbit这个AMQP的driver方式；
      加载配置文件oslo.messaging.notify.drivers中定义的notifier各种驱动实现方式；                      
    """
    
    """
    options.set_defaults:
    方法的作用是实现设置数据库的默认参数选项值；
    其默认的参数选项值如database_opts所设置；
    """
    options.set_defaults(sql_connection=_DEFAULT_SQL_CONNECTION,
                         sqlite_db='xdrs.sqlite')
    
    """
    可见这个方法实现的就是RPC若干参数选项默认值的设置和注册，包括：
    transport_url（default=None），
    rpc_backend（default='rabbit'）
    control_exchange（default='openstack'）；
    同时指定了control_exchange = xdrs作为参数选项的默认值，所以：
    control_exchange（default='xdrs'）；
    """
    rpc.set_defaults(control_exchange='xdrs')
    
    """
    这里实现了注册用于远程调试的参数选项默认值到系统中，
    其group_name为remote_debug；
    """
    debugger.register_cli_opts()
    
    """
    1.根据project = xdrs以及sys.argv = ['/usr/bin/xdrs-api']实现确定：
    prog = xdrs-api和所应用配置文件路径
    default_config_files = ['/usr/share/xdrs/xdrs-dist.conf', 
                            '/etc/xdrs/xdrs.conf']
    2.实现注册配置文件路径等参数选项到系统；
    3.获取xdrs命名空间；
    4.检测所有选项参数的正确性；
    注：
    1.这里调用的完全是oslo模块中的代码，所以不涉及到改动xdrs相关文件的问题，
    只需要保证输入数据的正确性即可；
    2.这里需要查询一下/usr/share/xdrs/xdrs-dist.conf和/etc/xdrs/xdrs.conf的作用和应用，
    当然此时只是确定了配置文件的位置，还没有具体应用配置文件；
    """
    cfg.CONF(argv[1:],
             project='xdrs',
             version=version.version_string(),
             default_config_files=default_config_files)
    
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
    rpc.init(cfg.CONF)