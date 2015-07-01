from oslo.config import cfg
from oslo import messaging

from xdrs.objects import base as objects_base
from xdrs import rpc


CONF = cfg.CONF
CONF.import_opt('xdrs_host_topic', 'xdrs.service')
CONF.import_opt('xdrs_global_topic', 'xdrs.service')


class HostRPCAPI(object):
    def __init__(self):
        super(HostRPCAPI, self).__init__()
        target = messaging.Target(topic=CONF.xdrs_host_topic)
        """
        objects_base.XdrsObjectSerializer需要进行进一步实现，还未完成；
        """
        serializer = objects_base.XdrsObjectSerializer()
        self.client = self.get_client(target, serializer)

    # Cells overrides this
    def get_client(self, target, serializer):
        return rpc.get_client(target,
                              serializer=serializer)
    
    def get_vm_cpu_data_by_vm_id(self, context, vm_id, host_name):
        cctxt = self.client.prepare(server = host_name)
        cctxt.cast(context, 'get_vm_cpu_data_by_vm_id', vm_id=vm_id)
    
    """
    ****************
    * host_meminfo *
    ****************
    """
    def get_meminfo_by_id(self, context, host_id):
        cctxt = self.client.prepare(server = host_id)
        cctxt.cast(context, 'get_meminfo_by_id')
        
    
    """
    *******************
    * vms on host ram *
    *******************
    """
    def get_vms_ram_on_specific(self, context, vms_list, host_uuid):
        cctxt = self.client.prepare(server = host_uuid)
        cctxt.cast(context, 'get_vms_ram_on_specific', vms_list=vms_list)
    
    def compute_host_cpu_mhz(self, context, host_uuid_temp):
        cctxt = self.client.prepare(server = host_uuid_temp)
        cctxt.cast(context, 'compute_host_cpu_mhz', host_uuid_temp=host_uuid_temp)
    
    
class HostToGlobalRPCAPI(object):
    def __init__(self):
        super(HostToGlobalRPCAPI, self).__init__()
        target = messaging.Target(topic=CONF.xdrs_global_topic)
        """
        objects_base.XdrsObjectSerializer需要进行进一步实现，还未完成；
        """
        serializer = objects_base.XdrsObjectSerializer()
        self.client = self.get_client(target, serializer)
    
    
    """
    **************
    * host_power *
    **************
    """
    def switch_host_off(self, context, sleep_command, host):
        cctxt = self.client.prepare(server = host)
        cctxt.cast(context, 'switch_host_off', sleep_command=sleep_command)
        
    def switch_host_on(self, context, ether_wake_interface, host_macs, host):
        cctxt = self.client.prepare(server = host)
        cctxt.cast(context, 'switch_host_on', 
                   ether_wake_interface=ether_wake_interface,
                   host_macs=host_macs)