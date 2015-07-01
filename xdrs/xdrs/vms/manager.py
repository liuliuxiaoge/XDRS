import webob
import libvirt

from xdrs import manager
from xdrs.vms import rpcapi as vms_rpcapi
from xdrs import conductor
import xdrs
from xdrs import vms
from xdrs import exception

class VmManager(manager.Manager):
    def __init__(self, compute_driver=None, *args, **kwargs):
        """
        Load configuration options and connect to the hypervisor.
        """
        self._last_host_check = 0
        self._last_bw_usage_poll = 0
        self._bw_usage_supported = True
        self._last_bw_usage_cell_update = 0
        
        self.vms_rpcapi = vms_rpcapi.VmRPCAPI()
        self.conductor_api = conductor.API()
        self._resource_tracker_dict = {}

        super(VmManager, self).__init__(service_name="hosts",
                                             *args, **kwargs)
    
    
    
    """
    ****************
    * vms_metadata *
    ****************
    """
    def get_all_vms_metadata(self, context):
        return self.conductor_api.get_all_vms_metadata(context)
    
    def get_vm_metadata_by_id(self, context, id):
        return self.conductor_api.get_vm_metadata_by_id(context, id)
    
    def get_vm_task_state_by_id(self, context, id):
        return self.conductor_api.get_vm_task_state_by_id(context, id)
    
    def delete_vm_metadata_by_id(self, context, id):
        """
        注：这个方法需要比较细致地来写；
        """
        """
        注：检测相应主机上的虚拟机实例是否存在，如果存在，则提示不能删除此虚拟机
        的元数据信息；
        """
        return self.conductor_api.delete_vm_metadata_by_id(context, id)
    
    
    
    """
    ***********************
    * vm_migration_record *
    ***********************
    """
    def get_all_vms_migration_records(self, context):
        return self.conductor_api.get_all_vms_migration_records(context)
            
    def get_vm_migration_record_by_id(self, context, id):
        return self.conductor_api.get_vm_migration_record_by_id(context, id)
            
    def create_vm_migration_record(self, context, vm_migration_record):
        return self.conductor_api.create_vm_migration_record(context, vm_migration_record)
            
    def delete_vm_migration_record_by_id(self, context, id):
        return self.conductor_api.delete_vm_migration_record_by_id(context, id)
            
    def get_specific_vm_migration_task_state(self, context, id):
        return self.conductor_api.get_specific_vm_migration_task_state(context, id)
            
    def get_specific_vm_all_migration_records(self, context, id):
        return self.conductor_api.get_specific_vm_all_migration_records(context, id)
            
    def get_specific_host_all_migration_records(self, context, id):
        return self.conductor_api.get_specific_host_all_migration_records(context, id)
            
    def get_specific_host_all_migration_in_records(self, context, id):
        return self.conductor_api.get_specific_host_all_migration_in_records(context, id)
            
    def get_specific_host_all_migration_out_records(self, context, id):
        return self.conductor_api.get_specific_host_all_migration_out_records(context, id)
    
    def init_host(self):
        """
        获取本地主机名；
        """
        local_host = ''
        context = xdrs.context.get_admin_context()
        self.vms_api = vms.API()
        
        try:
            vms_metadata = self.vms_api.get_all_vms_metadata(context)
        except exception.VmMetadataNotFound:
            msg = _('vm metadata not found')
            raise webob.exc.HTTPBadRequest(explanation=msg)
        
        if vms_metadata is None:
            vir_connection = libvirt.openReadOnly(local_host)
            vms_current = self._get_current_vms(vir_connection)
            
            for vm_uuid in vms_current:
                vm_create_values = {
                                    'host_id': local_host,
                                    'vm_id': vm_uuid,
                                    'vm_state': 'vm_normal'
                                    }
                
                vm_metadata = self.conductor_api.create_vm_metadata(context, vm_create_values)
        
     
    def _get_current_vms(self, vir_connection):
        """ 
        通过libvirt获取VM的UUID数据统计信息；
        """
        vm_uuids = {}
        for vm_id in vir_connection.listDomainsID():
            try:
                vm = vir_connection.lookupByID(vm_id)
                vm_uuids[vm.UUIDString()] = vm.state(0)[0]
            except libvirt.libvirtError:
                pass
        
        return vm_uuids   