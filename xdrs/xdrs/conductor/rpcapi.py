"""Client side of the conductor RPC API."""

from oslo.config import cfg
from oslo import messaging

from xdrs.objects import base as objects_base
from xdrs.openstack.common import jsonutils
from xdrs import rpc

CONF = cfg.CONF
CONF.import_opt('xdrs_conductor_topic', 'xdrs.service')
CONF.import_opt('upgrade_levels.conductor', 'xdrs.service')


class ConductorAPI(object):
    def __init__(self):
        super(ConductorAPI, self).__init__()
        target = messaging.Target(topic=CONF.xdrs_conductor_topic)
        version_cap = 1.0
        serializer = objects_base.XdrsObjectSerializer()
        self.client = rpc.get_client(target,
                                     version_cap=version_cap,
                                     serializer=serializer)
        
    def service_get_all_by(self, context, topic=None, host=None, binary=None):
        cctxt = self.client.prepare()
        return cctxt.call(context, 'service_get_all_by',
                          topic=topic, host=host, binary=binary)
        
    def service_create(self, context, values):
        cctxt = self.client.prepare()
        return cctxt.call(context, 'service_create', values=values)
    
    def service_destroy(self, context, service_id):
        cctxt = self.client.prepare()
        return cctxt.call(context, 'service_destroy', service_id=service_id)
    
    
    
    """
    **************
    * algorithms *
    **************
    """
    def get_all_algorithms_sorted_list(self, context): 
        cctxt = self.client.prepare()
        return cctxt.call(context, 'get_all_algorithms_sorted_list')
    
    def get_all_overload_algorithms_sorted_list(self, context):
        cctxt = self.client.prepare()
        return cctxt.call(context, 'get_all_overload_algorithms_sorted_list')

    def get_all_underload_algorithms_sorted_list(self, context):
        cctxt = self.client.prepare()
        return cctxt.call(context, 'get_all_underload_algorithms_sorted_list')
    
    def get_all_filter_scheduler_algorithms_sorted_list(self, context):
        cctxt = self.client.prepare()
        return cctxt.call(context, 'get_all_filter_scheduler_algorithms_sorted_list')
    
    def get_all_host_scheduler_algorithms_sorted_list(self, context): 
        cctxt = self.client.prepare()
        return cctxt.call(context, 'get_all_host_scheduler_algorithms_sorted_list')
    
    def get_all_vm_select_algorithm_sorted_list(self, context):
        cctxt = self.client.prepare()
        return cctxt.call(context, 'get_all_vm_select_algorithm_sorted_list')
    
    def get_overload_algorithm_by_id(self, context, id):
        cctxt = self.client.prepare()
        return cctxt.call(context, 'get_overload_algorithm_by_id', id=id)
    
    def get_underload_algorithm_by_id(self, context, id):
        cctxt = self.client.prepare()
        return cctxt.call(context, 'get_underload_algorithm_by_id', id=id)
    
    def get_filter_scheduler_algorithm_by_id(self, context, id):
        cctxt = self.client.prepare()
        return cctxt.call(context, 'get_filter_scheduler_algorithm_by_id', id=id)
    
    def get_host_scheduler_algorithm_by_id(self, context, id):
        cctxt = self.client.prepare()
        return cctxt.call(context, 'get_host_scheduler_algorithm_by_id', id=id)
    
    def get_vm_select_algorithm_by_id(self, context, id):
        cctxt = self.client.prepare()
        return cctxt.call(context, 'get_vm_select_algorithm_by_id', id=id)
    
    def delete_overload_algorithm_by_id(self, context, id):
        cctxt = self.client.prepare()
        return cctxt.call(context, 'delete_overload_algorithm_by_id', id=id)
    
    def delete_underload_algorithm_by_id(self, context, id):
        cctxt = self.client.prepare()
        return cctxt.call(context, 'delete_underload_algorithm_by_id', id=id)
    
    def delete_filter_scheduler_algorithm_by_id(self, context, id):
        cctxt = self.client.prepare()
        return cctxt.call(context, 'delete_filter_scheduler_algorithm_by_id', id=id)
    
    def delete_host_scheduler_algorithm_by_id(self, context, id):
        cctxt = self.client.prepare()
        return cctxt.call(context, 'delete_host_scheduler_algorithm_by_id', id=id)
    
    def delete_vm_select_algorithm_by_id(self, context, id):
        cctxt = self.client.prepare()
        return cctxt.call(context, 'delete_vm_select_algorithm_by_id', id=id)
    
    """
    注：这里应该改变配置文件中的参数信息，而不应该是改变数据库中的参数信息；
    """
    def update_overload_algorithm(self, context, id, values):
        values_p = jsonutils.to_primitive(values)
        cctxt = self.client.prepare()
        return cctxt.call(context, 'update_overload_algorithm', id=id, values=values_p)
    
    """
    注：这里应该改变配置文件中的参数信息，而不应该是改变数据库中的参数信息；
    """
    def update_underload_algorithm(self, context, id, values):
        values_p = jsonutils.to_primitive(values)
        cctxt = self.client.prepare()
        return cctxt.call(context, 'update_underload_algorithm', id=id, values=values_p)
    
    """
    注：这里应该改变配置文件中的参数信息，而不应该是改变数据库中的参数信息；
    """
    def update_filter_scheduler_algorithm(self, context, id, values):
        values_p = jsonutils.to_primitive(values)
        cctxt = self.client.prepare()
        return cctxt.call(context, 'update_filter_scheduler_algorithm', id=id, values=values_p)
    
    """
    注：这里应该改变配置文件中的参数信息，而不应该是改变数据库中的参数信息；
    """
    def update_host_scheduler_algorithm(self, context, id, values):
        values_p = jsonutils.to_primitive(values)
        cctxt = self.client.prepare()
        return cctxt.call(context, 'update_host_scheduler_algorithm', id=id, values=values_p)
    
    """
    注：这里应该改变配置文件中的参数信息，而不应该是改变数据库中的参数信息；
    """
    def update_vm_select_algorithm(self, context, id, values):
        values_p = jsonutils.to_primitive(values)
        cctxt = self.client.prepare()
        return cctxt.call(context, 'update_vm_select_algorithm', id=id, values=values_p)
    
    def create_underload_algorithm(self, context, algorithm_create_values):
        algorithm_create_values = jsonutils.to_primitive(algorithm_create_values)
        cctxt = self.client.prepare()
        return cctxt.call(context, 'create_underload_algorithm', algorithm_create_values=algorithm_create_values)
    
    def create_overload_algorithm(self, context, algorithm_create_values):
        algorithm_create_values = jsonutils.to_primitive(algorithm_create_values)
        cctxt = self.client.prepare()
        return cctxt.call(context, 'create_overload_algorithm', algorithm_create_values=algorithm_create_values)
    
    def create_filter_scheduler_algorithm(self, context, algorithm_create_values):
        algorithm_create_values = jsonutils.to_primitive(algorithm_create_values)
        cctxt = self.client.prepare()
        return cctxt.call(context, 'create_filter_scheduler_algorithm', algorithm_create_values=algorithm_create_values)
    
    def create_host_scheduler_algorithm(self, context, algorithm_create_values):
        algorithm_create_values = jsonutils.to_primitive(algorithm_create_values)
        cctxt = self.client.prepare()
        return cctxt.call(context, 'create_host_scheduler_algorithm', algorithm_create_values=algorithm_create_values)
    
    def create_vm_select_algorithm(self, context, algorithm_create_values):
        algorithm_create_values = jsonutils.to_primitive(algorithm_create_values)
        cctxt = self.client.prepare()
        return cctxt.call(context, 'create_vm_select_algorithm', algorithm_create_values=algorithm_create_values)
    
    def get_overload_algorithm_in_used(self, context):
        cctxt = self.client.prepare()
        return cctxt.call(context, 'get_overload_algorithm_in_used')

    def get_underload_algorithm_in_used(self, context):
        cctxt = self.client.prepare()
        return cctxt.call(context, 'get_underload_algorithm_in_used')

    def get_filter_scheduler_algorithms_in_used(self, context):
        cctxt = self.client.prepare()
        return cctxt.call(context, 'get_filter_scheduler_algorithms_in_used')
    
    def get_host_scheduler_algorithm_in_used(self, context):
        cctxt = self.client.prepare()
        return cctxt.call(context, 'get_host_scheduler_algorithm_in_used')
    
    def get_vm_select_algorithm_in_used(self, context):
        cctxt = self.client.prepare()
        return cctxt.call(context, 'get_vm_select_algorithm_in_used')
    
    """
    *****************
    * host_cpu_data *
    *****************
    """
    def get_all_host_cpu_data(self, context):
        cctxt = self.client.prepare()
        return cctxt.call(context, 'get_all_host_cpu_data')
    
    def get_host_cpu_data_by_id(self, context, id):
        cctxt = self.client.prepare()
        return cctxt.call(context, 'get_host_cpu_data_by_id', id=id)
    
    def create_host_cpu_data_temp_by_id(self, context, update_values, host_uuid):
        cctxt = self.client.prepare()
        update_value_p = jsonutils.to_primitive(update_values)
        return cctxt.call(
                   context, 
                   'create_host_cpu_data_temp_by_id', 
                   host_uuid=host_uuid, 
                   update_values=update_value_p)
    
    def update_host_cpu_data_temp_by_id(self, context, update_values, host_uuid):
        cctxt = self.client.prepare()
        update_value_p = jsonutils.to_primitive(update_values)
        return cctxt.call(
                   context, 
                   'update_host_cpu_data_temp_by_id', 
                   host_uuid=host_uuid, 
                   update_values=update_value_p)
    
    def get_host_cpu_data_temp_by_id(self, context, host_uuid):
        cctxt = self.client.prepare()
        return cctxt.call(context, 'get_host_cpu_data_temp_by_id', host_uuid=host_uuid)
    
    
    """
    *****************
    * hosts_states *
    *****************
    """
    def get_all_hosts_states(self, context):
        cctxt = self.client.prepare()
        return cctxt.call(context, 'get_all_hosts_states')
    
    def get_host_task_states_by_id(self, context, id):
        cctxt = self.client.prepare()
        return cctxt.call(context, 'get_host_task_states_by_id', id=id)
            
    def delete_host_task_states_by_id(self, context, id):
        cctxt = self.client.prepare()
        return cctxt.call(context, 'delete_host_task_states_by_id', id=id)
            
    def update_host_task_states(self, context, id, update_value):
        update_value_p = jsonutils.to_primitive(update_value)
        cctxt = self.client.prepare()
        return cctxt.call(context, 'update_host_task_states', id=id, values=update_value_p)
            
    def get_all_hosts_task_states_sorted_list(self, context):
        cctxt = self.client.prepare()
        return cctxt.call(context, 'get_all_hosts_task_states_sorted_list')
    
    def get_host_running_states_by_id(self, context, id):
        cctxt = self.client.prepare()
        return cctxt.call(context, 'get_host_running_states_by_id', id=id)
            
    def update_host_running_states(self, context, id, update_value):
        update_value_p = jsonutils.to_primitive(update_value)
        cctxt = self.client.prepare()
        return cctxt.call(context, 'update_host_running_states', id=id, values=update_value_p)
            
    def delete_host_running_states_by_id(self, context, id):
        cctxt = self.client.prepare()
        return cctxt.call(context, 'delete_host_running_states_by_id', id=id)
            
    def get_all_hosts_running_states_sorted_list(self, context):
        cctxt = self.client.prepare()
        return cctxt.call(context, 'get_all_hosts_running_states_sorted_list')
    
    def get_host_load_states_by_id(self, context, id):
        cctxt = self.client.prepare()
        return cctxt.call(context, 'get_host_load_states_by_id', id=id)
            
    def update_host_load_states(self, context, id, update_value):
        update_value_p = jsonutils.to_primitive(update_value)
        cctxt = self.client.prepare()
        return cctxt.call(context, 'update_host_load_states', id=id, values=update_value_p)
            
    def delete_host_load_states_by_id(self, context, id):
        cctxt = self.client.prepare()
        return cctxt.call(context, 'delete_host_load_states_by_id', id=id)
            
    def get_all_hosts_load_states_sorted_list(self, context):
        cctxt = self.client.prepare()
        return cctxt.call(context, 'get_all_hosts_load_states_sorted_list')
    
    
    
    """
    ******************
    * host_init_data *
    ******************
    """
    def create_host_init_data(self, context, update_values):
        update_values_p = jsonutils.to_primitive(update_values)
        cctxt = self.client.prepare()
        return cctxt.call(context, 'create_host_init_data', values=update_values_p)
    
    def update_host_init_data(self, context, host_id, update_values):
        update_values_p = jsonutils.to_primitive(update_values)
        cctxt = self.client.prepare()
        return cctxt.call(context, 'update_host_init_data', host_id, values=update_values_p)
    
    def get_host_init_data(self, context, host_id):
        cctxt = self.client.prepare()
        return cctxt.call(context, 'get_host_init_data', host_id)
    
    def get_all_hosts_init_data(self, context):
        cctxt = self.client.prepare()
        return cctxt.call(context, 'get_all_hosts_init_data')
    
    def create_host_init_data_temp(self, context, update_values):
        update_values_p = jsonutils.to_primitive(update_values)
        cctxt = self.client.prepare()
        return cctxt.call(context, 'create_host_init_data_temp', values=update_values_p)
    
    def update_host_init_data_temp(self, context, host_id, update_values):
        update_values_p = jsonutils.to_primitive(update_values)
        cctxt = self.client.prepare()
        return cctxt.call(context, 'update_host_init_data_temp', host_id, values=update_values_p)
    
    def get_host_init_data_temp(self, context, host_uuid_temp):
        cctxt = self.client.prepare()
        return cctxt.call(context, 'get_host_init_data_temp', host_uuid_temp)
    
    
    
    """
    ***************
    * vm_cpu_data *
    ***************
    """
    def get_all_vms_cpu_data(self, context):
        cctxt = self.client.prepare()
        return cctxt.call(context, 'get_all_vms_cpu_data')
            
    def get_vm_cpu_data_by_vm_id(self, context, vm_id):
        cctxt = self.client.prepare()
        return cctxt.call(context, 'get_vm_cpu_data_by_vm_id', vm_id)
            
    def delete_vm_cpu_data_by_vm_id(self, context, vm_id):
        cctxt = self.client.prepare()
        return cctxt.call(context, 'delete_vm_cpu_data_by_vm_id', vm_id)
    
    def get_vm_cpu_data_by_host_id(self, context, host_id):
        cctxt = self.client.prepare()
        return cctxt.call(context, 'get_vm_cpu_data_by_host_id', host_id)
    
    def delete_vm_cpu_data_by_host_id(self, context, host_id):
        cctxt = self.client.prepare()
        return cctxt.call(context, 'delete_vm_cpu_data_by_host_id', host_id)
    
    
    
    """
    ****************
    * vms_metadata *
    ****************
    """
    def get_all_vms_metadata(self, context):
        cctxt = self.client.prepare()
        return cctxt.call(context, 'get_all_vms_metadata')
    
    def get_vm_metadata_by_id(self, context, id):
        cctxt = self.client.prepare()
        return cctxt.call(context, 'get_vm_metadata_by_id', id=id)
    
    def get_vm_task_state_by_id(self, context, id):
        cctxt = self.client.prepare()
        return cctxt.call(context, 'get_vm_task_state_by_id', id=id)
    
    def delete_vm_metadata_by_id(self, context, id):
        """
        注：这个方法需要比较细致地来写；
        """
        cctxt = self.client.prepare()
        return cctxt.call(context, 'delete_vm_metadata_by_id', id=id)
    
    def create_vm_metadata(self, context, vm_create_values):
        """
        注：这个方法需要比较细致地来写；
        """
        cctxt = self.client.prepare()
        vm_create_values = jsonutils.to_primitive(vm_create_values)
        return cctxt.call(context, 'create_vm_metadata', vm_create_values=vm_create_values)
    
    
    
    
    """
    ***********************
    * vm_migration_record *
    ***********************
    """
    def get_all_vms_migration_records(self, context):
        cctxt = self.client.prepare()
        return cctxt.call(context, 'get_all_vms_migration_records')
            
    def get_vm_migration_record_by_id(self, context, id):
        cctxt = self.client.prepare()
        return cctxt.call(context, 'get_vm_migration_record_by_id', id=id)
            
    def create_vm_migration_record(self, context, vm_migration_record):
        cctxt = self.client.prepare()
        return cctxt.call(context, 'create_vm_migration_record', values=vm_migration_record)
            
    def delete_vm_migration_record_by_id(self, context, id):
        cctxt = self.client.prepare()
        return cctxt.call(context, 'delete_vm_migration_record_by_id', id=id)
            
    def get_specific_vm_migration_task_state(self, context, id):
        cctxt = self.client.prepare()
        return cctxt.call(context, 'get_specific_vm_migration_task_state', id=id)
            
    def get_specific_vm_all_migration_records(self, context, id):
        cctxt = self.client.prepare()
        return cctxt.call(context, 'get_specific_vm_all_migration_records', id=id)
            
    def get_specific_host_all_migration_records(self, context, id):
        cctxt = self.client.prepare()
        return cctxt.call(context, 'get_specific_host_all_migration_records', id=id)
            
    def get_specific_host_all_migration_in_records(self, context, id):
        cctxt = self.client.prepare()
        return cctxt.call(context, 'get_specific_host_all_migration_in_records', id=id)
            
    def get_specific_host_all_migration_out_records(self, context, id):
        cctxt = self.client.prepare()
        return cctxt.call(context, 'get_specific_host_all_migration_out_records', id=id)
