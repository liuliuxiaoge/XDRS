from sqlalchemy import or_
from oslo.config import cfg
import xdrs.context
from xdrs.db.sqlalchemy import models
from xdrs.openstack.common.db.sqlalchemy import session as db_session
from xdrs.openstack.common.db import exception as db_exc
from xdrs import exception


db_opts = [
    cfg.StrOpt('osapi_compute_unique_server_name_scope',
               default='',
               help='When set, compute API will consider duplicate hostnames '
                    'invalid within the specified scope, regardless of case. '
                    'Should be empty, "project" or "global".'),
]


connection_opts = [
    cfg.StrOpt('slave_connection',
               secret=True,
               help='The SQLAlchemy connection string used to connect to the '
                    'slave database'),
]


CONF = cfg.CONF
CONF.register_opts(db_opts)
CONF.register_opts(connection_opts, group='database')


_MASTER_FACADE = None
_SLAVE_FACADE = None


def _create_facade_lazily(use_slave=False):
    global _MASTER_FACADE
    global _SLAVE_FACADE

    return_slave = use_slave and CONF.database.slave_connection
    if not return_slave:
        if _MASTER_FACADE is None:
            _MASTER_FACADE = db_session.EngineFacade(
                CONF.database.connection,
                **dict(CONF.database.iteritems())
            )
        return _MASTER_FACADE
    else:
        if _SLAVE_FACADE is None:
            _SLAVE_FACADE = db_session.EngineFacade(
                CONF.database.slave_connection,
                **dict(CONF.database.iteritems())
            )
        return _SLAVE_FACADE

def get_session(use_slave=False, **kwargs):
    facade = _create_facade_lazily(use_slave)
    return facade.get_session(**kwargs)

def model_query(context, model, *args, **kwargs):
    use_slave = kwargs.get('use_slave') or False
    if CONF.database.slave_connection == '':
        use_slave = False

    session = kwargs.get('session') or get_session(use_slave=use_slave)
    read_deleted = kwargs.get('read_deleted') or context.read_deleted
    project_only = kwargs.get('project_only', False)

    def issubclassof_xdrs_base(obj):
        return isinstance(obj, type) and issubclass(obj, models.XdrsBase)

    base_model = model
    if not issubclassof_xdrs_base(base_model):
        base_model = kwargs.get('base_model', None)
        if not issubclassof_xdrs_base(base_model):
            raise Exception(_("model or base_model parameter should be "
                              "subclass of XdrsBase"))

    query = session.query(model, *args)

    default_deleted_value = base_model.__mapper__.c.deleted.default.arg
    if read_deleted == 'no':
        query = query.filter(base_model.deleted == default_deleted_value)
    elif read_deleted == 'yes':
        pass  # omit the filter to include deleted and active
    elif read_deleted == 'only':
        query = query.filter(base_model.deleted != default_deleted_value)
    else:
        raise Exception(_("Unrecognized read_deleted value '%s'")
                            % read_deleted)

    if xdrs.context.is_user_context(context) and project_only:
        if project_only == 'allow_none':
            query = query.\
                filter(or_(base_model.project_id == context.project_id,
                           base_model.project_id == None))
        else:
            query = query.filter_by(project_id=context.project_id)

    return query

def service_destroy(context, service_id):
    session = get_session()
    with session.begin():
        count = model_query(context, models.Service, session=session).\
                    filter_by(id=service_id).\
                    soft_delete(synchronize_session=False)

        if count == 0:
            raise exception.ServiceNotFound(service_id=service_id)

def _service_get(context, service_id, with_compute_node=True, session=None):
    query = model_query(context, models.Service, session=session).\
                     filter_by(id=service_id)

    result = query.first()
    if not result:
        raise exception.ServiceNotFound(service_id=service_id)

    return result

def service_get(context, service_id):
    return _service_get(context, service_id)

def service_create(context, values):
    service_ref = models.Service()
    service_ref.update(values)
    if not CONF.enable_new_services:
        service_ref.disabled = True
    try:
        service_ref.save()
    except db_exc.DBDuplicateEntry as e:
        if 'binary' in e.columns:
            raise exception.ServiceBinaryExists(host=values.get('host'),
                        binary=values.get('binary'))
        raise exception.ServiceTopicExists(host=values.get('host'),
                        topic=values.get('topic'))
    return service_ref

def service_update(context, service_id, values):
    session = get_session()
    with session.begin():
        service_ref = _service_get(context, service_id,
                                   with_compute_node=False, session=session)
        service_ref.update(values)

    return service_ref

def local_vm_metadata_creat(context, values):
    vm_metadata = models.VmMetadata()
    vm_metadata.update(values)
    vm_metadata.save()
    return vm_metadata

def local_vm_metadata_update(context, id, values):
    session = get_session()
    with session.begin():
        vm_metadata = model_query(context, models.VmMetadata, session=session,
                             read_deleted="no").\
                        filter_by(id = id).\
                        all()
        vm_metadata.update(values)
        session.add(vm_metadata)
    return vm_metadata

def local_vm_metadata_destroy(context, id):
    result = model_query(context, models.VmMetadata).\
                         filter_by(id = id).\
                         soft_delete()
    if not result:
        raise exception.LocalVmMetadataNotFound(id = id)

def local_vm_metadata_get(context, id):
    vm_metadata = model_query(context, models.VmMetadata).\
                        filter_by(id = id).\
                        all()
    if not vm_metadata:
        raise exception.LocalVmMetadataNotFound(id = id)
    return vm_metadata


"""
**************
* algorithms *
**************
"""
def algorithm_get_all(context):
    underload_algorithms = underload_algorithm_get_all(context)
    overloca_algorithms = overload_algorithm_get_all(context)
    filter_scheduler_algorithms = filter_scheduler_algorithm_get_all(context)
    host_scheduler_algorithms = host_scheduler_algorithm_get_all(context)
    
    return {'underload_algorithms':underload_algorithms,
            'overloca_algorithms':overloca_algorithms,
            'filter_scheduler_algorithms':filter_scheduler_algorithms,
            'host_scheduler_algorithms':host_scheduler_algorithms}
    
def underload_algorithm_get_all(context):
    underload_algorithms = model_query(context, models.UnderloadAlgorithms).\
                        all()
    if not underload_algorithms:
        raise exception.UnderloadAlgorithmsNotFound()
    return underload_algorithms

def overload_algorithm_get_all(context):
    overload_algorithms = model_query(context, models.OverloadAlgorithms).\
                        all()
    if not overload_algorithms:
        raise exception.OverloadAlgorithmsNotFound()
    return overload_algorithms

def filter_scheduler_algorithm_get_all(context):
    filter_scheduler_algorithms = model_query(context, models.FilterSchedulerAlgorithms).\
                        all()
    if not filter_scheduler_algorithms:
        raise exception.FilterSchedulerAlgorithmsNotFound()
    return filter_scheduler_algorithms

def host_scheduler_algorithm_get_all(context):
    host_scheduler_algorithms = model_query(context, models.HostSchedulerAlgorithms).\
                        all()
    if not host_scheduler_algorithms:
        raise exception.HostSchedulerAlgorithmsNotFound()
    return host_scheduler_algorithms

def overload_algorithm_get_by_id(context, id):
    overload_algorithm = model_query(context, models.OverloadAlgorithms).\
                        filter_by(id = id).\
                        all()
    if not overload_algorithm:
        raise exception.OverloadAlgorithmNotFound(id = id)
    return overload_algorithm

def underload_algorithm_get_by_id(context, id):
    underload_algorithm = model_query(context, models.UnderloadAlgorithms).\
                        filter_by(id = id).\
                        all()
    if not underload_algorithm:
        raise exception.UnderloadAlgorithmNotFound(id = id)
    return underload_algorithm

def filter_scheduler_algorithm_get_by_id(context, id):
    filter_scheduler_algorithm = model_query(context, models.FilterSchedulerAlgorithms).\
                        filter_by(id = id).\
                        all()
    if not filter_scheduler_algorithm:
        raise exception.FilterSchedulerAlgorithmNotFound(id = id)
    return filter_scheduler_algorithm

def host_scheduler_algorithm_get_by_id(context, id):
    host_scheduler_algorithm = model_query(context, models.HostSchedulerAlgorithms).\
                        filter_by(id = id).\
                        all()
    if not host_scheduler_algorithm:
        raise exception.HostSchedulerAlgorithmNotFound(id = id)
    return host_scheduler_algorithm

def overload_algorithm_delete_by_id(context, id):
    result = model_query(context, models.OverloadAlgorithms).\
                        filter_by(id = id).\
                        soft_delete()
                                         
    if not result:
        raise exception.OverloadAlgorithmNotFound(id = id)

def underload_algorithm_delete_by_id(context, id):
    result = model_query(context, models.UnderloadAlgorithms).\
                        filter_by(id = id).\
                        soft_delete()
    if not result:
        raise exception.UnderloadAlgorithmNotFound(id = id)

def filter_scheduler_algorithm_delete_by_id(context, id):
    result = model_query(context, models.FilterSchedulerAlgorithms).\
                        filter_by(id = id).\
                        soft_delete()
    if not result:
        raise exception.FilterSchedulerAlgorithmNotFound(id = id)

def host_scheduler_algorithm_delete_by_id(context, id):
    result = model_query(context, models.HostSchedulerAlgorithms).\
                        filter_by(id = id).\
                        soft_delete()
    if not result:
        raise exception.HostSchedulerAlgorithmNotFound(id = id)
    
def overload_algorithm_update(context, id, values):    
    result = model_query(context, models.OverloadAlgorithms).\
                   filter_by(id=id).\
                   update(values)
    if result == 0:
        raise exception.OverloadAlgorithmNotFound(id = id)
    
def underload_algorithm_update(context, id, values):    
    result = model_query(context, models.UnderloadAlgorithms).\
                   filter_by(id=id).\
                   update(values)
    if result == 0:
        raise exception.UnderloadAlgorithmNotFound(id = id)
    
def filter_scheduler_algorithm_update(context, id, values):    
    result = model_query(context, models.FilterSchedulerAlgorithms).\
                   filter_by(id=id).\
                   update(values)
    if result == 0:
        raise exception.FilterSchedulerAlgorithmNotFound(id = id)
    
def host_scheduler_algorithm_update(context, id, values):    
    result = model_query(context, models.HostSchedulerAlgorithms).\
                   filter_by(id=id).\
                   update(values)
    if result == 0:
        raise exception.HostSchedulerAlgorithmNotFound(id = id)
    
def vm_select_algorithm_update(self, context, id, values):
    result = model_query(context, models.VmSelectAlgorithms).\
                   filter_by(id=id).\
                   update(values)
    if result == 0:
        raise exception.HostSchedulerAlgorithmNotFound(id = id)

def underload_algorithm_create(self, context, algorithm_create_values):
    underload_algorithm = models.UnderloadAlgorithms()
    algorithm_name = algorithm_create_values['algorithm_name']
    algorithm_id = algorithm_create_values['algorithm_id']
    algorithm_parameters = algorithm_create_values['algorithm_parameters']
    description = algorithm_create_values['algorithm_description']
    in_use = algorithm_create_values['in_use']
    underload_algorithm.update(algorithm_name)
    underload_algorithm.update(algorithm_id)
    underload_algorithm.update(algorithm_parameters)
    underload_algorithm.update(description)
    underload_algorithm.update(in_use)
    underload_algorithm.save()
    return underload_algorithm
    
def overload_algorithm_create(self, context, algorithm_create_values):
    overload_algorithm = models.OverloadAlgorithms()
    algorithm_name = algorithm_create_values['algorithm_name']
    algorithm_id = algorithm_create_values['algorithm_id']
    algorithm_parameters = algorithm_create_values['algorithm_parameters']
    description = algorithm_create_values['algorithm_description']
    in_use = algorithm_create_values['in_use']
    overload_algorithm.update(algorithm_name)
    overload_algorithm.update(algorithm_id)
    overload_algorithm.update(algorithm_parameters)
    overload_algorithm.update(description)
    overload_algorithm.update(in_use)
    overload_algorithm.save()
    return overload_algorithm
    
def filter_scheduler_algorithm_create(self, context, algorithm_create_values):
    filter_scheduler_algorithm = models.FilterSchedulerAlgorithms()
    algorithm_name = algorithm_create_values['algorithm_name']
    algorithm_id = algorithm_create_values['algorithm_id']
    algorithm_parameters = algorithm_create_values['algorithm_parameters']
    description = algorithm_create_values['algorithm_description']
    in_use = algorithm_create_values['in_use']
    filter_scheduler_algorithm.update(algorithm_name)
    filter_scheduler_algorithm.update(algorithm_id)
    filter_scheduler_algorithm.update(algorithm_parameters)
    filter_scheduler_algorithm.update(description)
    filter_scheduler_algorithm.update(in_use)
    filter_scheduler_algorithm.save()
    return filter_scheduler_algorithm
    
def host_scheduler_algorithm_create(self, context, algorithm_create_values):
    host_scheduler_algorithm = models.HostSchedulerAlgorithms()
    algorithm_name = algorithm_create_values['algorithm_name']
    algorithm_id = algorithm_create_values['algorithm_id']
    algorithm_parameters = algorithm_create_values['algorithm_parameters']
    description = algorithm_create_values['algorithm_description']
    in_use = algorithm_create_values['in_use']
    host_scheduler_algorithm.update(algorithm_name)
    host_scheduler_algorithm.update(algorithm_id)
    host_scheduler_algorithm.update(algorithm_parameters)
    host_scheduler_algorithm.update(description)
    host_scheduler_algorithm.update(in_use)
    host_scheduler_algorithm.save()
    return host_scheduler_algorithm
    
def vm_select_algorithm_create(self, context, algorithm_create_values):
    vm_select_algorithm = models.VmSelectAlgorithms()
    algorithm_name = algorithm_create_values['algorithm_name']
    algorithm_id = algorithm_create_values['algorithm_id']
    algorithm_parameters = algorithm_create_values['algorithm_parameters']
    description = algorithm_create_values['algorithm_description']
    in_use = algorithm_create_values['in_use']
    vm_select_algorithm.update(algorithm_name)
    vm_select_algorithm.update(algorithm_id)
    vm_select_algorithm.update(algorithm_parameters)
    vm_select_algorithm.update(description)
    vm_select_algorithm.update(in_use)
    vm_select_algorithm.save()
    return vm_select_algorithm
    
def overload_algorithm_in_used_get(self, context):
    overload_algorithm = model_query(context, models.OverloadAlgorithms).\
                        filter_by(in_used = True).\
                        all()
    if not overload_algorithm:
        raise exception.OverloadAlgorithmNotFound()
    return overload_algorithm

def underload_algorithm_in_used_get(self, context):
    underload_algorithm = model_query(context, models.UnderloadAlgorithms).\
                        filter_by(in_used = True).\
                        all()
    if not underload_algorithm:
        raise exception.UnderloadAlgorithmNotFound()
    return underload_algorithm

def filter_scheduler_algorithms_in_used_get(self, context):
    filter_scheduler_algorithms = model_query(context, models.FilterSchedulerAlgorithms).\
                        filter_by(in_used = True).\
                        all()
    if not filter_scheduler_algorithms:
        raise exception.FilterSchedulerAlgorithmNotFound()
    return filter_scheduler_algorithms

def host_scheduler_algorithm_in_used_get(self, context):
    host_scheduler_algorithm = model_query(context, models.HostSchedulerAlgorithms).\
                        filter_by(in_used = True).\
                        all()
    if not host_scheduler_algorithm:
        raise exception.HostSchedulerAlgorithmNotFound()
    return host_scheduler_algorithm
    
def vm_select_algorithm_in_used_get(self, context):
    vm_select_algorithm = model_query(context, models.VmSelectAlgorithms).\
                        filter_by(in_used = True).\
                        all()
    if not vm_select_algorithm:
        raise exception.VmSelectAlgorithmNotFound()
    return vm_select_algorithm
    


"""
*****************
* host_cpu_data *
*****************
"""
def host_cpu_data_create(context, values):
    """
    暂未实现调用；
    """
    host_cpu_data = models.HostCpuData()
    host_cpu_data.update(values)
    host_cpu_data.save()
    return host_cpu_data

def host_cpu_data_update(context, host_id, values):
    """
    暂未实现调用；
    """
    session = get_session()
    with session.begin():
        host_cpu_data = model_query(context, models.HostCpuData, session=session,
                             read_deleted="no").\
                        filter_by(host_id = host_id).\
                        all()
        host_cpu_data.update(values)
        session.add(host_cpu_data)
    return host_cpu_data

def host_cpu_data_destroy(context, host_id):
    """
    暂未实现调用；
    """
    result = model_query(context, models.HostCpuData).\
                         filter_by(host_id = host_id).\
                         soft_delete()
    if not result:
        raise exception.HostCpuDataNotFound(host_id = host_id)
    
def hosts_cpu_data_get_all(context):
    hosts_cpu_data = model_query(context, models.HostCpuData).\
                        all()
    if not hosts_cpu_data:
        raise exception.HostCpuDataNotFound()
    return hosts_cpu_data

def host_cpu_data_get_by_id(context, host_id):
    host_cpu_data = model_query(context, models.HostCpuData).\
                        filter_by(host_id = host_id).\
                        all()
    if not host_cpu_data:
        raise exception.HostCpuDataNotFound(host_id = host_id)
    return host_cpu_data

def host_cpu_data_temp_create_by_id(context, update_values, host_uuid):
    host_cpu_data_temp = models.HostCpuDataTemp()
    cpu_data = update_values[0]
    host_ram_info = update_values[1]
    hosts_total_ram = host_ram_info['MemTotal']
    hosts_free_ram = host_ram_info['MemFree']
    host_cpu_data_temp.update(host_uuid)
    host_cpu_data_temp.update(cpu_data)
    host_cpu_data_temp.update(hosts_total_ram)
    host_cpu_data_temp.update(hosts_free_ram)
    host_cpu_data_temp.save()
    return host_cpu_data_temp

def host_cpu_data_temp_update_by_id(context, update_values, host_uuid):
    hosts_free_ram = update_values
    result = model_query(context, models.HostCpuDataTemp).\
                   filter_by(host_uuid=host_uuid).\
                   update(hosts_free_ram)
    if result == 0:
        raise exception.HostCpuDataNotFound(host_uuid = host_uuid)

def host_cpu_data_temp_get_by_id(self, context, host_uuid):
    host_cpu_data = model_query(context, models.HostCpuDataTemp).\
                        filter_by(host_uuid = host_uuid).\
                        all()
    if not host_cpu_data:
        raise exception.HostCpuDataNotFound(host_uuid = host_uuid)
    return host_cpu_data



"""
*****************
* hosts_states *
*****************
"""
def hosts_states_get_all(context):
    hosts_task_states = hosts_task_states_get_all(context)
    hosts_running_states = hosts_running_states_get_all(context)
    hosts_load_states = hosts_load_states_get_all(context)
    
    return {'hosts_task_states':hosts_task_states,
            'hosts_running_states':hosts_running_states,
            'hosts_load_states':hosts_load_states}
    
def host_task_states_get_by_id(context, id):
    host_task_states = model_query(context, models.HostTaskState).\
                        filter_by(id = id).\
                        all()
                        
    if not host_task_states:
        raise exception.HostTaskStateNotFound(id = id)
    return host_task_states
            
def host_task_states_delete_by_id(context, id):
    result = model_query(context, models.HostTaskState).\
                        filter_by(id = id).\
                        soft_delete()
                                         
    if not result:
        raise exception.HostTaskStateNotFound(id = id)
            
def host_task_states_update(context, id, update_value):
    result = model_query(context, models.HostTaskState).\
                   filter_by(id=id).\
                   update(update_value)
                   
    if result == 0:
        raise exception.HostTaskStateNotFound(id = id)
            
def hosts_task_states_get_all(context):
    hosts_task_states = model_query(context, models.HostTaskState).\
                        all()
                        
    if not hosts_task_states:
        raise exception.HostTaskStateNotFound()
    return hosts_task_states
    
def host_running_states_get_by_id(context, id):
    host_task_states = model_query(context, models.HostRunningState).\
                        filter_by(id = id).\
                        all()
                        
    if not host_task_states:
        raise exception.HostRunningStateNotFound(id = id)
    return host_task_states
            
def host_running_states_update(context, id, update_value):
    result = model_query(context, models.HostRunningState).\
                   filter_by(id=id).\
                   update(host_running_state = update_value)
                   
    if result == 0:
        raise exception.HostTaskStateNotFound(id = id)
            
def host_running_states_delete_by_id(context, id):
    result = model_query(context, models.HostRunningState).\
                        filter_by(id = id).\
                        soft_delete()
                                         
    if not result:
        raise exception.HostRunningStateNotFound(id = id)
            
def hosts_running_states_get_all(context):
    hosts_task_states = model_query(context, models.HostRunningState).\
                        all()
                        
    if not hosts_task_states:
        raise exception.HostRunningStateNotFound()
    return hosts_task_states
    
def host_load_states_get_by_id(context, id):
    host_task_states = model_query(context, models.HostLoadState).\
                        filter_by(id = id).\
                        all()
                        
    if not host_task_states:
        raise exception.HostLoadStateNotFound(id = id)
    return host_task_states
            
def host_load_states_update(context, id, update_value):
    result = model_query(context, models.HostLoadState).\
                   filter_by(id=id).\
                   update(update_value)
                   
    if result == 0:
        raise exception.HostLoadStateNotFound(id = id)
            
def host_load_states_delete_by_id(context, id):
    result = model_query(context, models.HostLoadState).\
                        filter_by(id = id).\
                        soft_delete()
                                         
    if not result:
        raise exception.HostLoadStateNotFound(id = id)
            
def hosts_load_states_get_all(context):
    hosts_task_states = model_query(context, models.HostLoadState).\
                        all()
                        
    if not hosts_task_states:
        raise exception.HostLoadStateNotFound()
    return hosts_task_states



"""
******************
* host_init_data *
******************
"""
def host_init_data_create(context, update_values):
    host_init_data = models.HostInitData()
    host_init_data.update(update_values)
    host_init_data.save()
    return host_init_data

def host_init_data_update(context, update_values, host_id):
    result = model_query(context, models.HostInitData).\
                   filter_by(host_id=host_id).\
                   update(update_values)
                   
    if result == 0:
        raise exception.HostInitDataNotFound(host_id = host_id)
    
def host_init_data_get(context, host_id):
    host_init_data = model_query(context, models.HostInitData).\
                        filter_by(host_id = host_id).\
                        all()
                        
    if not host_init_data:
        raise exception.HostInitDataNotFound(host_id = host_id)
    return host_init_data

def hosts_init_data_get_all(context):
    hosts_init_data = model_query(context, models.HostInitData).\
                        all()
                        
    if not hosts_init_data:
        raise exception.HostInitDataNotFound()
    return hosts_init_data

def host_init_data_temp_create(context, update_values):
    host_init_data = models.HostInitDataTemp()
    previous_host_cpu_time_total = update_values['previous_host_cpu_time_total']
    previous_host_cpu_time_busy = update_values['previous_host_cpu_time_busy']
    physical_cpu_mhz = update_values['physical_cpu_mhz']
    host_uuid = update_values['host_uuid']
    host_init_data.update(previous_host_cpu_time_total)
    host_init_data.update(previous_host_cpu_time_busy)
    host_init_data.update(physical_cpu_mhz)
    host_init_data.update(host_uuid)
    host_init_data.save()
    return host_init_data

def host_init_data_temp_update(context, update_values, host_id):
    result = model_query(context, models.HostInitDataTemp).\
                   filter_by(host_id=host_id).\
                   update(update_values)
                   
    if result == 0:
        raise exception.HostInitDataNotFound(host_id = host_id)
    
def host_init_data_temp_get(context, host_uuid_temp):
    host_init_data = model_query(context, models.HostInitDataTemp).\
                        filter_by(host_id = host_uuid_temp).\
                        all()
                        
    if not host_init_data:
        raise exception.HostInitDataNotFound(host_id = host_uuid_temp)
    return host_init_data



"""
***************
* vm_cpu_data *
***************
"""
def vms_cpu_data_get_all(self, context):
    vms_cpu_data = model_query(context, models.VmCpuData).\
                        all()
                        
    if not vms_cpu_data:
        raise exception.VmCpuDataNotFound()
    return vms_cpu_data
            
def vm_cpu_data_get_by_vm_id(self, context, vm_id):
    vm_cpu_date = model_query(context, models.VmCpuData).\
                        filter_by(vm_id = vm_id).\
                        all()
    if not vm_cpu_date:
        raise exception.VmCpuDataNotFound(vm_id = vm_id)
    return vm_cpu_date
            
def vm_cpu_data_delete_by_vm_id(self, context, vm_id):
    result = model_query(context, models.VmCpuData).\
                         filter_by(vm_id = vm_id).\
                         soft_delete()
    if not result:
        raise exception.VmCpuDataNotFound(vm_id = vm_id)
    
def vm_cpu_data_get_by_host_id(self, context, host_id):
    vms_cpu_date = model_query(context, models.VmCpuData).\
                        filter_by(host_id = host_id).\
                        all()
    if not vms_cpu_date:
        raise exception.VmCpuDataNotFound(host_id = host_id)
    return vms_cpu_date
    
def vm_cpu_data_delete_by_host_id(self, context, host_id):
    result = model_query(context, models.VmCpuData).\
                         filter_by(host_id = host_id).\
                         soft_delete()
    if not result:
        raise exception.VmCpuDataNotFound(host_id = host_id)



"""
****************
* vms_metadata *
****************
"""
def vms_metadata_get_all(self, context):
    vms_metadata = model_query(context, models.VmMetadata).\
                        all()
                        
    if not vms_metadata:
        raise exception.VmMetadataNotFound()
    return vms_metadata
    
def vm_metadata_get_by_id(self, context, id):
    vm_metadata = model_query(context, models.VmMetadata).\
                        filter_by(id = id).\
                        all()
                                         
    if not vm_metadata:
        raise exception.VmMetadataNotFound()
    return vm_metadata
    
def vm_task_state_get_by_id(self, context, id):
    vm_metadata = model_query(context, models.VmMetadata).\
                        filter_by(id = id).\
                        all()
                                         
    if not vm_metadata:
        raise exception.VmMetadataNotFound()
    return vm_metadata['vm_state']
    
def vm_metadata_delete_by_id(self, context, id):
    """
    注：这个方法需要比较细致地来写；
    """
    result = model_query(context, models.VmMetadata).\
                        filter_by(id = id).\
                        soft_delete()
                                         
    if not result:
        raise exception.VmMetadataNotFound(id = id)

def vm_metadata_create(self, context, vm_create_values):
    vm_metadata = models.VmMetadata()
    host_id = vm_create_values['host_id']
    vm_id = vm_create_values['vm_id']
    vm_state = vm_create_values['vm_state']
    vm_metadata.update(host_id)
    vm_metadata.update(vm_id)
    vm_metadata.update(vm_state)
    vm_metadata.save()
    return vm_metadata
 


"""
***********************
* vm_migration_record *
***********************
"""
def vms_migration_records_get_all(context):
    vms_migration_records = model_query(context, models.VmMigrationRecord).\
                        all()         
    if not vms_migration_records:
        raise exception.VmMigrationRecordNotFound()
    return vms_migration_records
            
def vm_migration_record_get_by_id(context, id):
    vm_migration_record = model_query(context, models.VmMigrationRecord).\
                        filter_by(id = id).\
                        all()
    if not vm_migration_record:
        raise exception.VmMigrationRecordNotFound(id = id)
    return vm_migration_record
            
def vm_migration_record_create(context, values):
    vm_migration_record = models.VmMigrationRecord()
    vm_migration_record.update(values)
    vm_migration_record.save()
    return vm_migration_record
            
def vm_migration_record_delete_by_id(context, id):
    result = model_query(context, models.VmMigrationRecord).\
                         filter_by(id = id).\
                         soft_delete()
    if not result:
        raise exception.VmMigrationRecordNotFound(id = id)
            
def specific_vm_migration_task_state_get(context, id):
    vm_migration_record = model_query(context, models.VmMigrationRecord).\
                        filter_by(id = id).\
                        all()
    vm_migration_task_state = vm_migration_record['task_state']
    
    if not vm_migration_record:
        raise exception.VmMigrationRecordNotFound(id = id)
    return vm_migration_record
            
def specific_vm_migration_records_get_all(context, id):
    vm_migration_records = model_query(context, models.VmMigrationRecord).\
                        filter_by(vm_id = id).\
                        all()
    if not vm_migration_records:
        raise exception.VmMigrationRecordNotFound(id = id)
    return vm_migration_records
            
def specific_host_migration_records_get_all(context, id):
    host_migration_in_records = specific_host_migration_in_records_get_all(context, id)
    host_migration_out_records = specific_host_migration_out_records_get_all(context, id)
    host_migration_records = host_migration_in_records+host_migration_out_records
    
    return host_migration_records
            
def specific_host_migration_in_records_get_all(context, id):
    host_migration_in_records = model_query(context, models.VmMigrationRecord).\
                        filter_by(current_host_id = id).\
                        all()
    if not host_migration_in_records:
        raise exception.HostMigrationRecordNotFound(id = id)
    return host_migration_in_records
            
def specific_host_migration_out_records_get_all(context, id):
    host_migration_out_records = model_query(context, models.VmMigrationRecord).\
                        filter_by(previous_host_id = id).\
                        all()
    if not host_migration_out_records:
        raise exception.HostMigrationRecordNotFound(id = id)
    return host_migration_out_records
