"""
用于处理所有到conductor服务的请求；
"""

from oslo.config import cfg
from oslo import messaging

from xdrs import baserpc
from xdrs.conductor import manager
from xdrs.conductor import rpcapi
from xdrs.openstack.common.gettextutils import _
from xdrs.openstack.common import log as logging
from xdrs import utils

conductor_opts = [
    cfg.BoolOpt('use_local',
                default=False),
    cfg.StrOpt('topic',
               default='conductor',
               help='The topic on which conductor nodes listen'),
    cfg.StrOpt('manager',
               default='xdrs.conductor.manager.ConductorManager',
               help='Full class name for the Manager for conductor'),
    cfg.IntOpt('workers',
               help='Number of workers for OpenStack Conductor service. '
                    'The default will be the number of CPUs available.')
]
conductor_group = cfg.OptGroup(name='conductor',
                               title='Conductor Options')
CONF = cfg.CONF
CONF.register_group(conductor_group)
CONF.register_opts(conductor_opts, conductor_group)

LOG = logging.getLogger(__name__)


class LocalAPI(object):
    """
    A local version of the conductor API that does database updates
    locally instead of via RPC.
    """

    def __init__(self):
        self._manager = utils.ExceptionHelper(manager.ConductorManager())

    def wait_until_ready(self, context, *args, **kwargs):
        pass

    def service_get_by_args(self, context, host, binary):
        return self._manager.service_get_all_by(context, host=host,
                                                binary=binary)

    def service_create(self, context, values):
        return self._manager.service_create(context, values)
    
    def service_destroy(self, context, service_id):
        return self._manager.service_destroy(context, service_id)
    
    def get_all_algorithms_sorted_list(self, context): 
        return self._manager.get_all_algorithms_sorted_list(context)
    
    def get_all_overload_algorithms_sorted_list(self, context):
        return self._manager.get_all_overload_algorithms_sorted_list(context)

    def get_all_underload_algorithms_sorted_list(self, context):
        return self._manager.get_all_underload_algorithms_sorted_list(context)
    
    def get_all_filter_scheduler_algorithms_sorted_list(self, context):
        return self._manager.get_all_filter_scheduler_algorithms_sorted_list(context)
    
    def get_all_host_scheduler_algorithms_sorted_list(self, context): 
        return self._manager.get_all_host_scheduler_algorithms_sorted_list(context)
    
    def get_all_vm_select_algorithm_sorted_list(self, context):
        return self._manager.get_all_vm_select_algorithm_sorted_list(context)
    
    def get_overload_algorithm_by_id(self, context, id):
        return self._manager.get_overload_algorithm_by_id(context, id)
    
    def get_underload_algorithm_by_id(self, context, id):
        return self._manager.get_underload_algorithm_by_id(context, id)
    
    def get_filter_scheduler_algorithm_by_id(self, context, id):
        return self._manager.get_filter_scheduler_algorithm_by_id(context, id)
    
    def get_host_scheduler_algorithm_by_id(self, context, id):
        return self._manager.get_host_scheduler_algorithm_by_id(context, id)
    
    def get_vm_select_algorithm_by_id(self, context, id):
        return self._manager.get_vm_select_algorithm_by_id(context, id)
    
    def delete_overload_algorithm_by_id(self, context, id):
        return self._manager.delete_overload_algorithm_by_id(context, id)
    
    def delete_underload_algorithm_by_id(self, context, id):
        return self._manager.delete_underload_algorithm_by_id(context, id)
    
    def delete_filter_scheduler_algorithm_by_id(self, context, id):
        return self._manager.delete_filter_scheduler_algorithm_by_id(context, id)
    
    def delete_host_scheduler_algorithm_by_id(self, context, id):
        return self._manager.delete_host_scheduler_algorithm_by_id(context, id)
    
    def delete_vm_select_algorithm_by_id(self, context, id):
        return self._manager.delete_vm_select_algorithm_by_id(context, id)
    
    """
    注：这里应该改变配置文件中的参数信息，而不应该是改变数据库中的参数信息；
    """
    def update_overload_algorithm(self, context, id, values):
        return self._manager.update_overload_algorithm(context, id, values)
    
    """
    注：这里应该改变配置文件中的参数信息，而不应该是改变数据库中的参数信息；
    """
    def update_underload_algorithm(self, context, id, values):
        return self._manager.update_underload_algorithm(context, id, values)
    
    """
    注：这里应该改变配置文件中的参数信息，而不应该是改变数据库中的参数信息；
    """
    def update_filter_scheduler_algorithm(self, context, id, values):
        return self._manager.update_filter_scheduler_algorithm(context, id, values)
    
    """
    注：这里应该改变配置文件中的参数信息，而不应该是改变数据库中的参数信息；
    """
    def update_host_scheduler_algorithm(self, context, id, values):
        return self._manager.update_host_scheduler_algorithm(context, id, values)
    
    """
    注：这里应该改变配置文件中的参数信息，而不应该是改变数据库中的参数信息；
    """
    def update_vm_select_algorithm(self, context, id, values):
        return self._manager.update_vm_select_algorithm(context, id, values)
    
    def get_overload_algorithm_in_used(self, context):
        return self._manager.get_overload_algorithm_in_used(context)

    def get_underload_algorithm_in_used(self, context):
        return self._manager.get_underload_algorithm_in_used(context)

    def get_filter_scheduler_algorithms_in_used(self, context):
        return self._manager.get_filter_scheduler_algorithms_in_used(context)

    def get_host_scheduler_algorithm_in_used(self, context):
        return self._manager.get_host_scheduler_algorithm_in_used(context)
    
    def get_vm_select_algorithm_in_used(self, context):
        return self._manager.get_vm_select_algorithm_in_used(context)
    
    """
    *****************
    * host_cpu_data *
    *****************
    """
    def get_all_host_cpu_data(self, context):
        return self._manager.get_all_host_cpu_data(context)
    
    def get_host_cpu_data_by_id(self, context, id):
        return self._manager.get_host_cpu_data_by_id(context, id)
    
    def create_host_cpu_data_temp_by_id(self, context, update_values, host_uuid):
        return self._manager.create_host_cpu_data_temp_by_id(context, update_values, host_uuid)
    
    def update_host_cpu_data_temp_by_id(self, context, update_values, host_uuid):
        return self._manager.update_host_cpu_data_temp_by_id(context, update_values, host_uuid)
    
    def get_host_cpu_data_temp_by_id(self, context, host_uuid):
        return self._manager.get_host_cpu_data_temp_by_id(context, host_uuid)
    
    
    
    """
    *****************
    * hosts_states *
    *****************
    """
    def get_all_hosts_states(self, context):
        return self._manager.get_all_hosts_states(context)
    
    def get_host_task_states_by_id(self, context, id):
        return self._manager.get_host_task_states_by_id(context, id)
            
    def delete_host_task_states_by_id(self, context, id):
        return self._manager.delete_host_task_states_by_id(context, id)
            
    def update_host_task_states(self, context, id, update_value):
        return self._manager.update_host_task_states(context, id, update_value)
            
    def get_all_hosts_task_states_sorted_list(self, context):
        return self._manager.get_all_hosts_task_states_sorted_list(context)     
    
    def get_host_running_states_by_id(self, context, id):
        return self._manager.get_host_running_states_by_id(context, id)
            
    def update_host_running_states(self, context, id, update_value):
        return self._manager.update_host_running_states(context, id, update_value)
            
    def delete_host_running_states_by_id(self, context, id):
        return self._manager.delete_host_running_states_by_id(context, id)
            
    def get_all_hosts_running_states_sorted_list(self, context):
        return self._manager.get_all_hosts_running_states_sorted_list(context)   
    
    def get_host_load_states_by_id(self, context, id):
        return self._manager.get_host_load_states_by_id(context, id)
            
    def update_host_load_states(self, context, id, update_value):
        return self._manager.update_host_load_states(context, id, update_value)
            
    def delete_host_load_states_by_id(self, context, id):
        return self._manager.delete_host_load_states_by_id(context, id)
            
    def get_all_hosts_load_states_sorted_list(self, context):
        return self._manager.get_all_hosts_load_states_sorted_list(context)
    
    
    
    """
    ******************
    * host_init_data *
    ******************
    """
    def create_host_init_data(self, context, update_values):
        return self._manager.create_host_init_data(context, update_values)
    
    def update_host_init_data(self, context, host_id, update_values):
        return self._manager.update_host_init_data(context, host_id, update_values)
    
    def get_host_init_data(self, context, host_id):
        return self._manager.get_host_init_data(context, host_id)
    
    def get_all_hosts_init_data(self, context):
        return self._manager.get_all_hosts_init_data(context)
    
    def create_host_init_data_temp(self, context, update_values):
        return self._manager.create_host_init_data_temp(context, update_values)
    
    def update_host_init_data_temp(self, context, host_id, update_values):
        return self._manager.update_host_init_data_temp(context, host_id, update_values)
    
    def get_host_init_data_temp(self, context, host_uuid_temp):
        return self._manager.get_host_init_data_temp(context, host_uuid_temp)
    
    
    
    """
    ***************
    * vm_cpu_data *
    ***************
    """
    def get_all_vms_cpu_data(self, context):
        return self._manager.get_all_vms_cpu_data(context)
            
    def get_vm_cpu_data_by_vm_id(self, context, vm_id):
        return self._manager.get_vm_cpu_data_by_vm_id(context, vm_id)
            
    def delete_vm_cpu_data_by_vm_id(self, context, vm_id):
        return self._manager.delete_vm_cpu_data_by_vm_id(context, vm_id)
    
    def get_vm_cpu_data_by_host_id(self, context, host_id):
        return self._manager.get_vm_cpu_data_by_host_id(context, host_id)
    
    def delete_vm_cpu_data_by_host_id(self, context, host_id):
        return self._manager.delete_vm_cpu_data_by_host_id(context, host_id)
    
    
    
    """
    ****************
    * vms_metadata *
    ****************
    """
    def get_all_vms_metadata(self, context):
        return self._manager.get_all_vms_metadata(context)
    
    def get_vm_metadata_by_id(self, context, id):
        return self._manager.get_vm_metadata_by_id(context, id)
    
    def get_vm_task_state_by_id(self, context, id):
        return self._manager.get_vm_task_state_by_id(context, id)
    
    def delete_vm_metadata_by_id(self, context, id):
        """
        注：这个方法需要比较细致地来写；
        """
        return self._manager.delete_vm_metadata_by_id(context, id)
    
    def create_vm_metadata(self, context, vm_create_values):
        return self._manager.create_vm_metadata(context, vm_create_values)
    
    
    
    """
    ***********************
    * vm_migration_record *
    ***********************
    """
    def get_all_vms_migration_records(self, context):
        return self._manager.get_all_vms_migration_records(context)
            
    def get_vm_migration_record_by_id(self, context, id):
        return self._manager.get_vm_migration_record_by_id(context, id)
            
    def create_vm_migration_record(self, context, vm_migration_record):
        return self._manager.create_vm_migration_record(context, vm_migration_record)
            
    def delete_vm_migration_record_by_id(self, context, id):
        return self._manager.delete_vm_migration_record_by_id(context, id)
            
    def get_specific_vm_migration_task_state(self, context, id):
        return self._manager.get_specific_vm_migration_task_state(context, id)
            
    def get_specific_vm_all_migration_records(self, context, id):
        return self._manager.get_specific_vm_all_migration_records(context, id)
            
    def get_specific_host_all_migration_records(self, context, id):
        return self._manager.get_specific_host_all_migration_records(context, id)
            
    def get_specific_host_all_migration_in_records(self, context, id):
        return self._manager.get_specific_host_all_migration_in_records(context, id)
            
    def get_specific_host_all_migration_out_records(self, context, id):
        return self._manager.get_specific_host_all_migration_out_records(context, id)
    
    

class LocalComputeTaskAPI(object):
    def __init__(self):
        self._manager = utils.ExceptionHelper(
                manager.ComputeTaskManager())

    def resize_instance(self, context, instance, extra_instance_updates,
                        scheduler_hint, flavor, reservations):
        self._manager.migrate_server(
            context, instance, scheduler_hint, False, False, flavor,
            None, None, reservations)

    def live_migrate_instance(self, context, instance, host_name,
                              block_migration, disk_over_commit):
        scheduler_hint = {'host': host_name}
        self._manager.migrate_server(
            context, instance, scheduler_hint, True, False, None,
            block_migration, disk_over_commit, None)

    def build_instances(self, context, instances, image,
            filter_properties, admin_password, injected_files,
            requested_networks, security_groups, block_device_mapping,
            legacy_bdm=True):
        utils.spawn_n(self._manager.build_instances, context,
                instances=instances, image=image,
                filter_properties=filter_properties,
                admin_password=admin_password, injected_files=injected_files,
                requested_networks=requested_networks,
                security_groups=security_groups,
                block_device_mapping=block_device_mapping,
                legacy_bdm=legacy_bdm)

    def unshelve_instance(self, context, instance):
        utils.spawn_n(self._manager.unshelve_instance, context,
                instance=instance)


class API(LocalAPI):
    """
    Conductor API that does updates via RPC to the ConductorManager.
    注：系统默认调用的是class API而不是class LocalAPI，也就是说系统默认的情况是不是所有的
    计算节点上都装了xdrs-conductor组件，当某一节点上没有装这个组件，那么就需要同过rpc消息队列
    实现远程方法的调用，之所以默认为这种情况，因为无法保证用户在安装openstack的时候在每个计算节点上
    都安装xdrs-conductor组件；再看class API这个类下，实现的方法很少（都是确定无论在何种情况下肯定
    要应用远程消息调用的方法），而且这个类是继承于类LocalAPI，这样设计的好处就是，先在API这个类下
    查找要调用的方法，如果找到说明这个方法是无论如何都要应用远程消息调用的机制，如果没有找到相匹配的
    方法，则会调用其父类LocalAPI中的这个方法，而此时self._manager覆盖了父类中的self._manager，使得父类
    中的方法调用也会应用远程消息调用的机制，这样做的好处就是，不用在类API中，再重写一遍所有方法的实现，
    减少了代码量。
    当然，如果系统默认调用的是class LocalAPI，则说明每个计算节点都安装了组件xdrs-conductor，这样就不需要
    使用远程消息调用机制来实现方法的调用，而类LocalAPI中的self._manager也不会被类API中的self._manager所覆盖，
    也就不会应用远程消息调用机制。
    """

    def __init__(self):
        self._manager = rpcapi.ConductorAPI()
        self.base_rpcapi = baserpc.BaseAPI(topic=CONF.conductor.topic)

    def wait_until_ready(self, context, early_timeout=10, early_attempts=10):
        '''
        Wait until a conductor service is up and running.

        This method calls the remote ping() method on the conductor topic until
        it gets a response.  It starts with a shorter timeout in the loop
        (early_timeout) up to early_attempts number of tries.  It then drops
        back to the globally configured timeout for rpc calls for each retry.
        '''
        attempt = 0
        timeout = early_timeout
        while True:
            if attempt == early_attempts:
                timeout = None
            attempt += 1

            try:
                self.base_rpcapi.ping(context, '1.21 GigaWatts',
                                      timeout=timeout)
                break
            except messaging.MessagingTimeout:
                LOG.warning(_('Timed out waiting for xdrs-conductor. '
                                'Is it running? Or did this service start '
                                'before xdrs-conductor?'))