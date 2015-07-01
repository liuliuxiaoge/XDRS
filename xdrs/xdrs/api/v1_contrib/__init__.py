"""
xdrs附加的API扩展内容；
"""

from oslo.config import cfg

from xdrs.api.openstack import extensions
from xdrs.openstack.common import log as logging

ext_opts = [
    cfg.ListOpt('osapi_compute_ext_list',
                default=[]),
]
CONF = cfg.CONF
CONF.register_opts(ext_opts)

LOG = logging.getLogger(__name__)


def standard_extensions(ext_mgr):
    """
    ======================================================================================
    ext_mgr = <nova.api.openstack.compute.extensions.ExtensionManager object at 0x33d9190>
    __path__ = ['/usr/lib/python2.7/site-packages/nova/api/openstack/compute/contrib']
    LOG = <nova.openstack.common.log.ContextAdapter object at 0x295d610>
    __package__ = nova.api.openstack.compute.contrib
    ======================================================================================
    """
    extensions.load_standard_extensions(ext_mgr, LOG, __path__, __package__)


def select_extensions(ext_mgr):
    extensions.load_standard_extensions(ext_mgr, LOG, __path__, __package__,
                                        CONF.osapi_compute_ext_list)