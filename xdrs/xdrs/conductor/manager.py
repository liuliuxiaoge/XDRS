"""Handles database requests from other xdrs services."""

from oslo import messaging

from xdrs import manager
from xdrs.openstack.common import log as logging


LOG = logging.getLogger(__name__)


class ConductorManager(manager.Manager):
    target = messaging.Target(version='1.64')

    """
    这里需要进行进一步分析；
    """
    def __init__(self, *args, **kwargs):
        super(ConductorManager, self).__init__(service_name='conductor',
                                               *args, **kwargs)
        self._compute_api = None
        self.additional_endpoints.append(self.compute_task_mgr)
    
    def service_destroy(self, context, service_id):
        return self.manager.service_destroy(context, service_id)
    
    
    
    """
    **************
    * algorithms *
    **************
    """
    def get_all_overload_algorithms_sorted_list(self, context):
        return self.db.overload_algorithm_get_all(context)

    def get_all_underload_algorithms_sorted_list(self, context):
        return self.db.underload_algorithm_get_all(context)

    def get_all_filter_scheduler_algorithms_sorted_list(self, context):
        return self.db.filter_scheduler_algorithm_get_all(context)

    def get_all_host_scheduler_algorithms_sorted_list(self, context):
        return self.db.host_scheduler_algorithm_get_all(context)
    
    def get_all_vm_select_algorithm_sorted_list(self, context):
        return self.db.vm_select_algorithm_get_all(context)

    def get_overload_algorithm_by_id(self, context, id):
        return self.db.overload_algorithm_get_by_id(context, id)

    def get_underload_algorithm_by_id(self, context, id):
        return self.db.underload_algorithm_get_by_id(context, id)

    def get_filter_scheduler_algorithm_by_id(self, context, id):
        return self.db.filter_scheduler_algorithm_get_by_id(context, id)

    def get_host_scheduler_algorithm_by_id(self, context, id):
        return self.db.host_scheduler_algorithm_get_by_id(context, id)
    
    def get_vm_select_algorithm_by_id(self, context, id):
        return self.db.vm_select_algorithm_get_by_id(context, id)

    def delete_overload_algorithm_by_id(self, context, id):
        return self.db.overload_algorithm_delete_by_id(context, id)

    def delete_underload_algorithm_by_id(self, context, id):
        return self.db.underload_algorithm_delete_by_id(context, id)

    def delete_filter_scheduler_algorithm_by_id(self, context, id):
        return self.db.filter_scheduler_algorithm_delete_by_id(context, id)

    def delete_host_scheduler_algorithm_by_id(self, context, id):
        return self.db.host_scheduler_algorithm_delete_by_id(context, id)
    
    def delete_vm_select_algorithm_by_id(self, context, id):
        return self.db.vm_select_algorithm_delete_by_id(context, id)

    """
    注：这里应该改变配置文件中的参数信息，而不应该是改变数据库中的参数信息；
    """
    def update_overload_algorithm(self, context, id, values):
        return self.db.overload_algorithm_update(context, id, values)

    """
    注：这里应该改变配置文件中的参数信息，而不应该是改变数据库中的参数信息；
    """
    def update_underload_algorithm(self, context, id, values):
        return self.db.underload_algorithm_update(context, id, values)

    """
    注：这里应该改变配置文件中的参数信息，而不应该是改变数据库中的参数信息；
    """
    def update_filter_scheduler_algorithm(self, context, id, values):
        return self.db.filter_scheduler_algorithm_update(context, id, values)

    """
    注：这里应该改变配置文件中的参数信息，而不应该是改变数据库中的参数信息；
    """
    def update_host_scheduler_algorithm(self, context, id, values):
        return self.db.host_scheduler_algorithm_update(context, id, values)
    
    """
    注：这里应该改变配置文件中的参数信息，而不应该是改变数据库中的参数信息；
    """
    def update_vm_select_algorithm(self, context, id, values):
        return self.db.vm_select_algorithm_update(context, id, values)
    
    def create_underload_algorithm(self, context, algorithm_create_values):
        return self.db.underload_algorithm_create(context, algorithm_create_values)
    
    def create_overload_algorithm(self, context, algorithm_create_values):
        return self.db.overload_algorithm_create(context, algorithm_create_values)
    
    def create_filter_scheduler_algorithm(self, context, algorithm_create_values):
        return self.db.filter_scheduler_algorithm_create(context, algorithm_create_values)
    
    def create_host_scheduler_algorithm(self, context, algorithm_create_values):
        return self.db.host_scheduler_algorithm_create(context, algorithm_create_values)
    
    def create_vm_select_algorithm(self, context, algorithm_create_values):
        return self.db.vm_select_algorithm_create(context, algorithm_create_values)
    
    def get_overload_algorithm_in_used(self, context):
        return self.db.overload_algorithm_in_used_get(context)

    def get_underload_algorithm_in_used(self, context):
        return self.db.underload_algorithm_in_used_get(context)

    def get_filter_scheduler_algorithms_in_used(self, context):
        return self.db.filter_scheduler_algorithms_in_used_get(context)

    def get_host_scheduler_algorithm_in_used(self, context):
        return self.db.host_scheduler_algorithm_in_used_get(context)
    
    def get_vm_select_algorithm_in_used(self, context):
        return self.db.vm_select_algorithm_in_used_get(context)
    
    """
    *****************
    * host_cpu_data *
    *****************
    """
    def get_all_host_cpu_data(self, context):
        return self.db.hosts_cpu_data_get_all(context)
    
    def get_host_cpu_data_by_id(self, context, id):
        return self.db.host_cpu_data_get_by_id(context, id)
    
    def create_host_cpu_data_temp_by_id(self, context, update_values, host_uuid):
        return self.db.host_cpu_data_temp_create_by_id(context, update_values, host_uuid)
    
    def update_host_cpu_data_temp_by_id(self, context, update_values, host_uuid):
        return self.db.host_cpu_data_temp_update_by_id(context, update_values, host_uuid)
    
    def get_host_cpu_data_temp_by_id(self, context, host_uuid):
        return self.db.host_cpu_data_temp_get_by_id(context, host_uuid)
    
    
    
    """
    *****************
    * hosts_states *
    *****************
    """
    def get_all_hosts_states(self, context):
        return self.db.hosts_states_get_all(context)
    
    def get_host_task_states_by_id(self, context, id):
        return self.db.host_task_states_get_by_id(context, id)
            
    def delete_host_task_states_by_id(self, context, id):
        return self.db.host_task_states_delete_by_id(context, id)
            
    def update_host_task_states(self, context, id, update_value):
        return self.db.host_task_states_update(context, id, update_value)
            
    def get_all_hosts_task_states_sorted_list(self, context):
        return self.db.hosts_task_states_get_all(context)     
    
    def get_host_running_states_by_id(self, context, id):
        return self.db.host_running_states_get_by_id(context, id)
            
    def update_host_running_states(self, context, id, update_value):
        return self.db.host_running_states_update(context, id, update_value)
            
    def delete_host_running_states_by_id(self, context, id):
        return self.db.host_running_states_delete_by_id(context, id)
            
    def get_all_hosts_running_states_sorted_list(self, context):
        return self.db.hosts_running_states_get_all(context)   
    
    def get_host_load_states_by_id(self, context, id):
        return self.db.host_load_states_get_by_id(context, id)
            
    def update_host_load_states(self, context, id, update_value):
        return self.db.host_load_states_update(context, id, update_value)
            
    def delete_host_load_states_by_id(self, context, id):
        return self.db.host_load_states_delete_by_id(context, id)
            
    def get_all_hosts_load_states_sorted_list(self, context):
        return self.db.hosts_load_states_get_all(context)
    
    
    """
    ******************
    * host_init_data *
    ******************
    """
    def create_host_init_data(self, context, update_values):
        return self.db.host_init_data_create(context, update_values)
    
    def update_host_init_data(self, context, host_id, update_values):
        return self.db.host_init_data_update(context, host_id, update_values)
    
    def get_host_init_data(self, context, host_id):
        return self.db.host_init_data_get(context, host_id)
    
    def get_all_hosts_init_data(self, context):
        return self.db.hosts_init_data_get_all(context)
    
    def create_host_init_data_temp(self, context, update_values):
        return self.db.host_init_data_temp_create(context, update_values)
    
    def update_host_init_data_temp(self, context, host_id, update_values):
        return self.db.host_init_data_temp_update(context, host_id, update_values)
    
    def get_host_init_data_temp(self, context, host_uuid_temp):
        return self.db.host_init_data_temp_get(context, host_uuid_temp)
    
    
    
    """
    ***************
    * vm_cpu_data *
    ***************
    """
    def get_all_vms_cpu_data(self, context):
        return self.db.vms_cpu_data_get_all(context)
            
    def get_vm_cpu_data_by_vm_id(self, context, vm_id):
        return self.db.vm_cpu_data_get_by_vm_id(context, vm_id)
            
    def delete_vm_cpu_data_by_vm_id(self, context, vm_id):
        return self.db.vm_cpu_data_delete_by_vm_id(context, vm_id)
    
    def get_vm_cpu_data_by_host_id(self, context, host_id):
        return self.db.vm_cpu_data_get_by_host_id(context, host_id)
    
    def delete_vm_cpu_data_by_host_id(self, context, host_id):
        return self.db.vm_cpu_data_delete_by_host_id(context, host_id)
    
    
    
    """
    ****************
    * vms_metadata *
    ****************
    """
    def get_all_vms_metadata(self, context):
        return self.db.vms_metadata_get_all(context)
    
    def get_vm_metadata_by_id(self, context, id):
        return self.db.vm_metadata_get_by_id(context)
    
    def get_vm_task_state_by_id(self, context, id):
        return self.db.vm_task_state_get_by_id(context)
    
    def delete_vm_metadata_by_id(self, context, id):
        """
        注：这个方法需要比较细致地来写；
        """
        return self.db.vm_metadata_delete_by_id(context, id)
    
    def create_vm_metadata(self, context, vm_create_values):
        return self.db.vm_metadata_create(context, vm_create_values)





    """
    ***********************
    * vm_migration_record *
    ***********************
    """
    def get_all_vms_migration_records(self, context):
        return self.db.vms_migration_records_get_all(context)
            
    def get_vm_migration_record_by_id(self, context, id):
        return self.db.vm_migration_record_get_by_id(context, id)
            
    def create_vm_migration_record(self, context, vm_migration_record):
        return self.db.vm_migration_record_create(context, id)
            
    def delete_vm_migration_record_by_id(self, context, id):
        return self.db.vm_migration_record_delete_by_id(context, id)
            
    def get_specific_vm_migration_task_state(self, context, id):
        return self.db.specific_vm_migration_task_state_get(context, id)
            
    def get_specific_vm_all_migration_records(self, context, id):
        return self.db.specific_vm_migration_records_get_all(context, id)
            
    def get_specific_host_all_migration_records(self, context, id):
        return self.db.specific_host_migration_records_get_all(context, id)
            
    def get_specific_host_all_migration_in_records(self, context, id):
        return self.db.specific_host_migration_in_records_get_all(context, id)
            
    def get_specific_host_all_migration_out_records(self, context, id):
        return self.db.specific_host_migration_out_records_get_all(context, id)