"""
这里还只是应用了方法：
def register_cli_opts()
其他方法的应用会一步步地进行验证；
"""

import sys


def enabled():
    return ('--remote_debug-host' in sys.argv and
            '--remote_debug-port' in sys.argv)


"""
可见方法register_cli_opts实现了注册用于远程调试的参数选项默认值到
系统中，其group_name为remote_debug；
"""
def register_cli_opts():
    from oslo.config import cfg

    CONF = cfg.CONF
    CONF.import_opt('remote_debug.host', 'xdrs.service')
    CONF.import_opt('remote_debug.port', 'xdrs.service')

def init():
    from oslo.config import cfg
    CONF = cfg.CONF

    if 'remote_debug' not in CONF:
        return

    if not (CONF.remote_debug.host and CONF.remote_debug.port):
        return

    from xdrs.openstack.common.gettextutils import _
    from xdrs.openstack.common import log as logging
    LOG = logging.getLogger(__name__)

    LOG.debug(_('Listening on %(host)s:%(port)s for debug connection'),
              {'host': CONF.remote_debug.host,
               'port': CONF.remote_debug.port})

    from pydev import pydevd
    pydevd.settrace(host=CONF.remote_debug.host,
                    port=CONF.remote_debug.port,
                    stdoutToServer=False,
                    stderrToServer=False)