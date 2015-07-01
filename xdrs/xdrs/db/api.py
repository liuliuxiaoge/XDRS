from oslo.config import cfg
from xdrs.openstack.common.db import api as db_api

CONF = cfg.CONF
_BACKEND_MAPPING = {'sqlalchemy': 'xdrs.db.sqlalchemy.api'}
IMPL = db_api.DBAPI(CONF.database.backend, backend_mapping=_BACKEND_MAPPING,
                    lazy=True)

def service_destroy(context, service_id):
    return IMPL.service_destroy(context, service_id)

def service_get(context, service_id):
    return IMPL.service_get(context, service_id)

def service_create(context, values):
    return IMPL.service_create(context, values)

def service_update(context, service_id, values):
    return IMPL.service_update(context, service_id, values)



def local_vm_metadata_creat(context, values):
    return IMPL.local_vm_metadata_creat(context, values)

def local_vm_metadata_update(context, id, values):
    return IMPL.local_vm_metadata_update(context, id, values)

def local_vm_metadata_destroy(context, id):
    return IMPL.local_vm_metadata_destroy(context, id)

def local_vm_metadata_get(context, id):
    return IMPL.local_vm_metadata_get(context, id)




def vm_migrations_create(context, values):
    return IMPL.vm_migrations_create(context, values)

def vm_migrations_update(context, id, values):
    return IMPL.vm_migrations_update(context, id, values)

def vm_migrations_destroy(context, id):
    return IMPL.vm_migrations_destroy(context, id)

def vm_migrations_get(context, id):
    return IMPL.vm_migrations_get(context, id)




def local_host_create(context, values):
    return IMPL.local_host_create(context, values)

def local_host_update(context, id, values):
    return IMPL.local_host_update(context, id, values)

def local_host_get(context, id):
    return IMPL.local_host_get(context, id)

def local_host_destroy(context, id):
    return IMPL.local_host_destroy(context, id)




def data_collector_init_create(context, values):
    return IMPL.data_collector_init_create(context, values)

def data_collector_init_update(context, host_id, values):
    return IMPL.data_collector_init_update(context, host_id, values)

def data_collector_init_destroy(context, host_id):
    return IMPL.data_collector_init_destroy(context, host_id)

def data_collector_init_get(context, host_id):
    return IMPL.data_collector_init_get(context, host_id)



def vm_cpu_data_create(context, values):
    return IMPL.vm_cpu_data_create(context, values)

def vm_cpu_data_update(context, vm_id, values):
    return IMPL.vm_cpu_data_update(context, vm_id, values)

def vm_cpu_data_destroy(context, vm_id):
    return IMPL.vm_cpu_data_destroy(context, vm_id)

def vm_cpu_data_get(context, vm_id):
    return IMPL.vm_cpu_data_get(context, vm_id)


"""
**************
* algorithms *
**************
"""
def algorithm_get_all(context):
    return IMPL.algorithm_get_all(context)

def underload_algorithm_get_all(context):
    return IMPL.underload_algorithm_get_all(context)

def overload_algorithm_get_all(context):
    return IMPL.overload_algorithm_get_all(context)

def filter_scheduler_algorithm_get_all(context):
    return IMPL.filter_scheduler_algorithm_get_all(context)

def host_scheduler_algorithm_get_all(context):
    return IMPL.host_scheduler_algorithm_get_all(context)

def vm_select_algorithm_get_all(self, context):
    return IMPL.vm_select_algorithm_get_all(context)

def overload_algorithm_get_by_id(context, id):
    return IMPL.overload_algorithm_get_by_id(context, id)

def underload_algorithm_get_by_id(context, id):
    return IMPL.underload_algorithm_get_by_id(context, id)

def filter_scheduler_algorithm_get_by_id(context, id):
    return IMPL.filter_scheduler_algorithm_get_by_id(context, id)

def host_scheduler_algorithm_get_by_id(context, id):
    return IMPL.host_scheduler_algorithm_get_by_id(context, id)

def vm_select_algorithm_get_by_id(self, context, id):
    return IMPL.vm_select_algorithm_get_by_id(context, id)

def overload_algorithm_delete_by_id(context, id):
    return IMPL.overload_algorithm_delete_by_id(context, id)

def underload_algorithm_delete_by_id(context, id):
    return IMPL.underload_algorithm_delete_by_id(context, id)

def filter_scheduler_algorithm_delete_by_id(context, id):
    return IMPL.filter_scheduler_algorithm_delete_by_id(context, id)

def host_scheduler_algorithm_delete_by_id(context, id):
    return IMPL.host_scheduler_algorithm_delete_by_id(context, id)

def vm_select_algorithm_delete_by_id(self, context, id):
    return IMPL.vm_select_algorithm_delete_by_id(context, id)

def overload_algorithm_update(context, id, values):
    return IMPL.overload_algorithm_update(context, id, values)

def underload_algorithm_update(context, id, values):
    return IMPL.underload_algorithm_update(context, id, values)

def filter_scheduler_algorithm_update(context, id, values):
    return IMPL.filter_scheduler_algorithm_update(context, id, values)

def host_scheduler_algorithm_update(context, id, values):
    return IMPL.host_scheduler_algorithm_update(context, id, values)

def vm_select_algorithm_update(self, context, id, values):
    return IMPL.vm_select_algorithm_update(context, id, values)

def underload_algorithm_create(self, context, algorithm_create_values):
    return IMPL.underload_algorithm_create(context, algorithm_create_values)
    
def overload_algorithm_create(self, context, algorithm_create_values):
    return IMPL.overload_algorithm_create(context, algorithm_create_values)
    
def filter_scheduler_algorithm_create(self, context, algorithm_create_values):
    return IMPL.filter_scheduler_algorithm_create(context, algorithm_create_values)
    
def host_scheduler_algorithm_create(self, context, algorithm_create_values):
    return IMPL.host_scheduler_algorithm_create(context, algorithm_create_values)
    
def vm_select_algorithm_create(self, context, algorithm_create_values):
    return IMPL.vm_select_algorithm_create(context, algorithm_create_values)
    
def overload_algorithm_in_used_get(self, context):
    return IMPL.overload_algorithm_in_used_get(context)

def underload_algorithm_in_used_get(self, context):
    return IMPL.underload_algorithm_in_used_get(context)

def filter_scheduler_algorithms_in_used_get(self, context):
    return IMPL.filter_scheduler_algorithms_in_used_get(context)

def host_scheduler_algorithm_in_used_get(self, context):
    return IMPL.host_scheduler_algorithm_in_used_get(context)
    
def vm_select_algorithm_in_used_get(self, context):
    return IMPL.vm_select_algorithm_in_used_get(context)



"""
*****************
* host_cpu_data *
*****************
"""
def hosts_cpu_data_get_all(context):
    return IMPL.hosts_cpu_data_get_all(context)

def host_cpu_data_create(context, values):
    """
    暂未实现调用；
    """
    return IMPL.host_cpu_data_create(context, values)

def host_cpu_data_update(context, host_id, values):
    """
    暂未实现调用；
    """
    return IMPL.host_cpu_data_update(context, host_id, values)

def host_cpu_data_destroy(context, host_id):
    """
    暂未实现调用；
    """
    return IMPL.host_cpu_data_destroy(context, host_id)

def host_cpu_data_get_by_id(context, host_id):
    return IMPL.host_cpu_data_get_by_id(context, host_id)

def host_cpu_data_temp_create_by_id(context, update_values, host_uuid):
    return IMPL.host_cpu_data_temp_create_by_id(context, update_values, host_uuid)

def host_cpu_data_temp_update_by_id(context, update_values, host_uuid):
    return IMPL.host_cpu_data_temp_update_by_id(context, update_values, host_uuid)

def host_cpu_data_temp_get_by_id(self, context, host_uuid):
    return IMPL.db.host_cpu_data_temp_get_by_id(context, host_uuid)
    
    


"""
*****************
* hosts_states *
*****************
"""
def hosts_states_get_all(context):
    return IMPL.hosts_states_get_all(context)
    
def host_task_states_get_by_id(context, id):
    return IMPL.host_task_states_get_by_id(context, id)
            
def host_task_states_delete_by_id(context, id):
    return IMPL.host_task_states_delete_by_id(context, id)
            
def host_task_states_update(context, id, update_value):
    return IMPL.host_task_states_update(context, id, update_value)
            
def hosts_task_states_get_all(context):
    return IMPL.hosts_task_states_get_all(context)     
    
def host_running_states_get_by_id(context, id):
    return IMPL.host_running_states_get_by_id(context, id)
            
def host_running_states_update(context, id, update_value):
    return IMPL.host_running_states_update(context, id, update_value)
            
def host_running_states_delete_by_id(context, id):
    return IMPL.host_running_states_delete_by_id(context, id)
            
def hosts_running_states_get_all(context):
    return IMPL.hosts_running_states_get_all(context)   
    
def host_load_states_get_by_id(context, id):
    return IMPL.host_load_states_get_by_id(context, id)
            
def host_load_states_update(context, id, update_value):
    return IMPL.host_load_states_update(context, id, update_value)
            
def host_load_states_delete_by_id(context, id):
    return IMPL.host_load_states_delete_by_id(context, id)
            
def hosts_load_states_get_all(context):
    return IMPL.hosts_load_states_get_all(context)


"""
******************
* host_init_data *
******************
"""
def host_init_data_create(context, update_values):
    return IMPL.host_init_data_create(context, update_values)
    
def host_init_data_update(context, host_id, update_values):
    return IMPL.host_init_data_update(context, host_id, update_values)

def host_init_data_get(self, context, host_id):
    return IMPL.host_init_data_get(context, host_id)

def hosts_init_data_get_all(self, context):
    return IMPL.hosts_init_data_get_all(context)

def host_init_data_temp_create(context, update_values):
    return IMPL.host_init_data_temp_create(context, update_values)

def host_init_data_temp_update(context, host_id, update_values):
    return IMPL.host_init_data_temp_update(context, host_id, update_values)

def host_init_data_temp_get(self, context, host_uuid_temp):
    return IMPL.host_init_data_temp_get(context, host_uuid_temp)



"""
***************
* vm_cpu_data *
***************
"""
def vms_cpu_data_get_all(self, context):
    return IMPL.vms_cpu_data_get_all(context)
            
def vm_cpu_data_get_by_vm_id(self, context, vm_id):
    return IMPL.vm_cpu_data_get_by_vm_id(context, vm_id)
            
def vm_cpu_data_delete_by_vm_id(self, context, vm_id):
    return IMPL.vm_cpu_data_delete_by_vm_id(context, vm_id)
    
def vm_cpu_data_get_by_host_id(self, context, host_id):
    return IMPL.vm_cpu_data_get_by_host_id(context, host_id)
    
def vm_cpu_data_delete_by_host_id(self, context, host_id):
    return IMPL.vm_cpu_data_delete_by_host_id(context, host_id)



"""
****************
* vms_metadata *
****************
"""
def vms_metadata_get_all(context):
    return IMPL.vms_metadata_get_all(context)
    
def vm_metadata_get_by_id(context, id):
    return IMPL.vm_metadata_get_by_id(context)
    
def vm_task_state_get_by_id(context, id):
    return IMPL.vm_task_state_get_by_id(context)
    
def vm_metadata_delete_by_id(context, id):
    """
    注：这个方法需要比较细致地来写；
    """
    return IMPL.vm_metadata_delete_by_id(context, id)

def vm_metadata_create(self, context, vm_create_values):
    return IMPL.vm_metadata_create(context, vm_create_values)




"""
***********************
* vm_migration_record *
***********************
"""
def vms_migration_records_get_all(context):
    return IMPL.vms_migration_records_get_all(context)
            
def vm_migration_record_get_by_id(context, id):
    return IMPL.vm_migration_record_get_by_id(context, id)
            
def vm_migration_record_create(context, values):
    return IMPL.vm_migration_record_create(context, values)
            
def vm_migration_record_delete_by_id(context, id):
    return IMPL.vm_migration_record_delete_by_id(context, id)
            
def specific_vm_migration_task_state_get(context, id):
    return IMPL.specific_vm_migration_task_state_get(context, id)
            
def specific_vm_migration_records_get_all(context, id):
    return IMPL.specific_vm_migration_records_get_all(context, id)
            
def specific_host_migration_records_get_all(context, id):
    return IMPL.specific_host_migration_records_get_all(context, id)
            
def specific_host_migration_in_records_get_all(context, id):
    return IMPL.specific_host_migration_in_records_get_all(context, id)
            
def specific_host_migration_out_records_get_all(context, id):
    return IMPL.specific_host_migration_out_records_get_all(context, id)