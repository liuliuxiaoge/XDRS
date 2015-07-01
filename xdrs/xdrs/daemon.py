"""
守护进程的控制实现；
"""

import os
import sys
import signal

from xdrs import utils


class Daemon(object):
    """Daemon base class"""

    def __init__(self, conf):
        self.conf = conf

    def run_once(self, *args, **kwargs):
        """Override this to run the script once"""
        raise NotImplementedError('run_once not implemented')

    def run_forever(self, *args, **kwargs):
        """Override this to run forever"""
        raise NotImplementedError('run_forever not implemented')

    def run(self, once=False, **kwargs):
        """Run the daemon"""
        
        """
        根据用户信息，设置当前进程的userid/groupid，并获取session leader等；
        注：如果实现了配置文件xdrs-load-dection.conf，则即可在配置文件中定义
        user = xdrs，即可向如下这样实现信息的获取；
        utils.drop_privileges(self.conf.get('user', 'xdrs'))
        """
        utils.drop_privileges(user='xdrs')
        
        """
        记录未处理的异常，关闭标准输入，捕获输出和错误。
        注：这里暂不实现，但是可以作为面试的一个重点来看；
        utils.capture_stdio(self.logger, **kwargs)
        """

        def kill_children(*args):
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
            os.killpg(0, signal.SIGTERM)
            sys.exit()

        signal.signal(signal.SIGTERM, kill_children)
        if once:
            self.run_once(**kwargs)
        else:
            self.run_forever(**kwargs)


def run_daemon(klass, conf_file, once=False, **kwargs):
    """
    注：这里conf_file指向的是xdrs-controller所对应的配置文件，日后此处可以进行
    功能扩展，如在守护进程启动的过程中，按照需求从配置文件中读取需要的参数信息等，
    添加到变量kwargs中，以供后续程序加载。
    """
    klass().run(once=once, **kwargs)