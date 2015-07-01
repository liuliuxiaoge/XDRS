from oslo.config import cfg

from xdrs.api.openstack import extensions as base_extensions
from xdrs.openstack.common.gettextutils import _
from xdrs.openstack.common import log as logging


ext_opts = [
    cfg.MultiStrOpt('osapi_compute_extension',
                    default=[
                      'xdrs.api.openstack.compute.contrib.standard_extensions'
                      ],
                    help='osapi compute extension to load'),
]
CONF = cfg.CONF
CONF.register_opts(ext_opts)


LOG = logging.getLogger(__name__)

class ExtensionManager(base_extensions.ExtensionManager):
    def __init__(self):
        LOG.audit(_('Initializing extension manager.'))
        self.cls_list = CONF.osapi_compute_extension
        """
        self.cls_list = xdrs.api.openstack.compute.contrib.standard_extensions
        """
        self.extensions = {}
        self.sorted_ext_list = []
        """
        实现加载所有的API扩展功能；
        """
        self._load_extensions()
