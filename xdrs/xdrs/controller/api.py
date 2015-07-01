"""
Handles all requests relating to compute resources (e.g. guest VMs,
networking and storage of VMs, and compute hosts on which they run).
"""

import functools

from oslo.config import cfg
from xdrs.controller import rpcapi as controller_rpcapi
from xdrs.controller import manager as manager
from xdrs.db import base
from xdrs import exception
from xdrs.openstack.common import log as logging
from xdrs import rpc

LOG = logging.getLogger(__name__)

get_notifier = functools.partial(rpc.get_notifier, service='global')
wrap_exception = functools.partial(exception.wrap_exception,
                                   get_notifier=get_notifier)

CONF = cfg.CONF
CONF.import_opt('controller', 'xdrs.service')

class API(base.Base):
    """
    API for interacting with the host manager.
    """

    def __init__(self, **kwargs):
        self.controller_rpcapi = controller_rpcapi.ControllerRPCAPI()
        self.manager = manager.ControllerManager()
        self.notifier = rpc.get_notifier('controller', CONF.controller)

        super(API, self).__init__(**kwargs)
    
    """
    ********************
    * vm_host_miration *
    ********************
    """
    def vm_to_host_migrate(self, context=None, vm, host):
        if context is None:
            context = context.get_admin_context()
        
        return self.manager.vm_to_host_migrate(context, vm, host)
    
    
    """
    **************
    * host_power *
    **************
    """
    def switch_host_off(self, context=None, sleep_command, host):
        if context is None:
            context = context.get_admin_context()
        
        return self.hosts_rpcapi.switch_host_off(context, sleep_command, host)
    
    def switch_host_on(self, context, ether_wake_interface, host_macs, host):
        if context is None:
            context = context.get_admin_context()
        
        return self.hosts_rpcapi.switch_host_on(context, 
                                               ether_wake_interface, 
                                               host_macs,
                                               host)
        
    def dynamic_resource_scheduling(self, context=None, reported):
        if context is None:
            context = context.get_admin_context()
        
        """
        reported相关的处理操作；
        """
        return self.manager.dynamic_resource_scheduling(context)