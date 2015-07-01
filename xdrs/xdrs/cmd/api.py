"""
Starter script for Xdrs API.
"""

import sys

from oslo.config import cfg

from xdrs import config
from xdrs.openstack.common import log as logging
from xdrs.openstack.common.report import guru_meditation_report as gmr
from xdrs import utils
from xdrs import version
from xdrs import service

CONF = cfg.CONF

def main():
    """
    @@@@还要进行解析；
    """
    config.parse_args(sys.argv)
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
    @@@@还要进行解析；
    """
    logging.setup("xdrs")
    """
    注：日志的操作，这里并不是重点，因此放在后面进行验证实现；
    """
    
    utils.monkey_patch()
    """
    注：动态组件的导入，这里并不是重点，因此放在后面进行验证实现（结合cinder的实现，因为要比nova简洁一些）；
    """
    """
    @@@@还要进行解析；
    """

    """
    gmr.TextGuruMeditation.setup_autorun(version)------xdrs测试作用；
    """
    """
    这个Guru Meditation Reports是用于获取xdrs的二进制运行时文件的状态的
    （当然啦实际的信息比这个多得多，因为可以自己写信号句柄）。
    原理很简单：通过发送一个USER1的信号量，进程捕获后会返回对应的信息。
    注：这里也不是重点，因此放在后面进行验证实现（弄清功能以确定其是否需要）；
    """
    gmr.TextGuruMeditation.setup_autorun(version)
    """
    @@@@还要进行解析；
    """
    
    """
    @@@@还要进行解析；
    """
    launcher = service.process_launcher()
    server = service.WSGIService('osapi_xdrs')
    launcher.launch_service(server, workers=server.workers or 1)
    launcher.wait()