"""
Handles all requests relating to compute resources (e.g. guest VMs,
networking and storage of VMs, and compute hosts on which they run).
"""

import functools
from webob import exc

from oslo.config import cfg
from xdrs.hosts import rpcapi as hosts_rpcapi
from xdrs.hosts import manager as manager
from xdrs import vms
from xdrs.db import base
from xdrs import exception
from xdrs import rpc
import xdrs


get_notifier = functools.partial(rpc.get_notifier, service='compute')
wrap_exception = functools.partial(exception.wrap_exception,
                                   get_notifier=get_notifier)

CONF = cfg.CONF


def check_instance_state(vm_state=None, task_state=(None,),
                         must_have_launched=True):
    """Decorator to check VM and/or task state before entry to API functions.

    If the instance is in the wrong state, or has not been successfully
    started at least once the wrapper will raise an exception.
    """

    if vm_state is not None and not isinstance(vm_state, set):
        vm_state = set(vm_state)
    if task_state is not None and not isinstance(task_state, set):
        task_state = set(task_state)

    def outer(f):
        @functools.wraps(f)
        def inner(self, context, instance, *args, **kw):
            if vm_state is not None and instance['vm_state'] not in vm_state:
                raise exception.InstanceInvalidState(
                    attr='vm_state',
                    instance_uuid=instance['uuid'],
                    state=instance['vm_state'],
                    method=f.__name__)
            if (task_state is not None and
                    instance['task_state'] not in task_state):
                raise exception.InstanceInvalidState(
                    attr='task_state',
                    instance_uuid=instance['uuid'],
                    state=instance['task_state'],
                    method=f.__name__)
            if must_have_launched and not instance['launched_at']:
                raise exception.InstanceInvalidState(
                    attr=None,
                    not_launched=True,
                    instance_uuid=instance['uuid'],
                    state=instance['vm_state'],
                    method=f.__name__)

            return f(self, context, instance, *args, **kw)
        return inner
    return outer


def check_instance_host(function):
    @functools.wraps(function)
    def wrapped(self, context, instance, *args, **kwargs):
        if not instance['host']:
            raise exception.InstanceNotReady(instance_id=instance['uuid'])
        return function(self, context, instance, *args, **kwargs)
    return wrapped


def check_instance_lock(function):
    @functools.wraps(function)
    def inner(self, context, instance, *args, **kwargs):
        if instance['locked'] and not context.is_admin:
            raise exception.InstanceIsLocked(instance_uuid=instance['uuid'])
        return function(self, context, instance, *args, **kwargs)
    return inner


def check_instance_cell(fn):
    def _wrapped(self, context, instance, *args, **kwargs):
        self._validate_cell(instance, fn.__name__)
        return fn(self, context, instance, *args, **kwargs)
    _wrapped.__name__ = fn.__name__
    return _wrapped


def require_admin_context(f):
    """
    Decorator to require admin request context.
    The first argument to the wrapped function must be the context.
    """

    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        xdrs.context.require_admin_context(args[0])
        return f(*args, **kwargs)
    return wrapper


class API(base.Base):
    """
    API for interacting with the host manager.
    """

    def __init__(self, **kwargs):
        self.hosts_rpcapi = hosts_rpcapi.HostRPCAPI()
        self.manager = manager.HostManager()
        self.notifier = rpc.get_notifier('hosts', CONF.host)

        super(API, self).__init__(**kwargs)
    
    
    """
    **************
    * algorithms *
    **************
    """
    def get_all_algorithms_sorted_list(self, context=None):
        """
        Get all non-deleted flavors as a sorted list.
        Pass true as argument if you want deleted flavors returned also.
        """
        """
        ======================================================================================
        ctxt = <nova.context.RequestContext object at 0x557c3d0>
        filters = {'is_public': True}
        sort_key = flavorid
        sort_dir = asc
        limit = None
        marker = None
        ======================================================================================     
        """
        if context is None:
            context = context.get_admin_context()
        
        return self.manager.get_all_algorithms_sorted_list(context)
    
    def get_all_overload_algorithms_sorted_list(self, context=None):
        if context is None:
            context = context.get_admin_context()
            
        return self.manager.get_all_overload_algorithms_sorted_list(context)

    def get_all_underload_algorithms_sorted_list(self, context=None):
        if context is None:
            context = context.get_admin_context()
    
        return self.manager.get_all_underload_algorithms_sorted_list(context)

    def get_all_filter_scheduler_algorithms_sorted_list(self, context=None):
        if context is None:
            context = context.get_admin_context()
    
        return self.manager.get_all_filter_scheduler_algorithms_sorted_list(context)

    def get_all_host_scheduler_algorithms_sorted_list(self, context=None):
        if context is None:
            context = context.get_admin_context()
    
        return self.manager.get_all_host_scheduler_algorithms_sorted_list(context)
    
    def get_all_vm_select_algorithm_sorted_list(self, context=None):
        if context is None:
            context = context.get_admin_context()
    
        return self.manager.get_all_vm_select_algorithm_sorted_list(context)

    def get_overload_algorithm_by_id(self, context=None, id):
        if context is None:
            context = context.get_admin_context()
    
        return self.manager.get_overload_algorithm_by_id(context, id)

    def get_underload_algorithm_by_id(self, context=None, id):
        if context is None:
            context = context.get_admin_context()
    
        return self.manager.get_underload_algorithm_by_id(context, id)

    def get_filter_scheduler_algorithm_by_id(self, context=None, id):
        if context is None:
            context = context.get_admin_context()
    
        return self.manager.get_filter_scheduler_algorithm_by_id(context, id)

    def get_host_scheduler_algorithm_by_id(self, context=None, id):
        if context is None:
            context = context.get_admin_context()
    
        return self.manager.get_host_scheduler_algorithm_by_id(context, id)
    
    def get_vm_select_algorithm_by_id(self, context=None, id):
        if context is None:
            context = context.get_admin_context()
    
        return self.manager.get_vm_select_algorithm_by_id(context, id)

    def delete_overload_algorithm_by_id(self, context=None, id):
        if context is None:
            context = context.get_admin_context()
    
        return self.manager.delete_overload_algorithm_by_id(context, id)

    def delete_underload_algorithm_by_id(self, context=None, id):
        if context is None:
            context = context.get_admin_context()
    
        return self.manager.delete_underload_algorithm_by_id(context, id)

    def delete_filter_scheduler_algorithm_by_id(self, context=None, id):
        if context is None:
            context = context.get_admin_context()
    
        return self.manager.delete_filter_scheduler_algorithm_by_id(context, id)

    def delete_host_scheduler_algorithm_by_id(self, context=None, id):
        if context is None:
            context = context.get_admin_context()
    
        return self.manager.delete_host_scheduler_algorithm_by_id(context, id)
    
    def delete_vm_select_algorithm_by_id(self, context=None, id):
        if context is None:
            context = context.get_admin_context()
    
        return self.manager.delete_vm_select_algorithm_by_id(context, id)
    
    """
    注：这里应该改变配置文件中的参数信息，而不应该是改变数据库中的参数信息；
    """
    @require_admin_context
    def update_overload_algorithm(self, context=None, id, values):
        if context is None:
            context = context.get_admin_context()
    
        return self.manager.update_overload_algorithm(context, id, values)

    """
    注：这里应该改变配置文件中的参数信息，而不应该是改变数据库中的参数信息；
    """
    @require_admin_context
    def update_underload_algorithm(self, context=None, id, values):
        if context is None:
            context = context.get_admin_context()
    
        return self.manager.update_underload_algorithm(context, id, values)

    """
    注：这里应该改变配置文件中的参数信息，而不应该是改变数据库中的参数信息；
    """
    @require_admin_context
    def update_filter_scheduler_algorithm(self, context=None, id, values):
        if context is None:
            context = context.get_admin_context()
    
        return self.manager.update_filter_scheduler_algorithm(context, id, values)

    """
    注：这里应该改变配置文件中的参数信息，而不应该是改变数据库中的参数信息；
    """
    @require_admin_context
    def update_host_scheduler_algorithm(self, context=None, id, values):
        if context is None:
            context = context.get_admin_context()
    
        return self.manager.update_host_scheduler_algorithm(context, id, values)
    
    """
    注：这里应该改变配置文件中的参数信息，而不应该是改变数据库中的参数信息；
    """
    @require_admin_context
    def update_vm_select_algorithm(self, context=None, id, values):
        if context is None:
            context = context.get_admin_context()
    
        return self.manager.update_vm_select_algorithm(context, id, values)
    
    def create_underload_algorithm(self, context=None, algorithm_create_values):
        if context is None:
            context = context.get_admin_context()
    
        return self.manager.create_underload_algorithm(context, algorithm_create_values)
    
    def create_overload_algorithm(self, context=None, algorithm_create_values):
        if context is None:
            context = context.get_admin_context()
    
        return self.manager.create_overload_algorithm(context, algorithm_create_values)
    
    def create_filter_scheduler_algorithm(self, context=None, algorithm_create_values):
        if context is None:
            context = context.get_admin_context()
    
        return self.manager.create_filter_scheduler_algorithm(context, algorithm_create_values)
    
    def create_host_scheduler_algorithm(self, context=None, algorithm_create_values):
        if context is None:
            context = context.get_admin_context()
    
        return self.manager.create_host_scheduler_algorithm(context, algorithm_create_values)
    
    def create_vm_select_algorithm(self, context=None, algorithm_create_values):
        if context is None:
            context = context.get_admin_context()
    
        return self.manager.create_vm_select_algorithm(context, algorithm_create_values)
    
    def get_overload_algorithm_in_used(self, context=None):
        if context is None:
            context = context.get_admin_context()
    
        return self.manager.get_overload_algorithm_in_used(context)

    def get_underload_algorithm_in_used(self, context=None):
        if context is None:
            context = context.get_admin_context()
    
        return self.manager.get_underload_algorithm_in_used(context)

    def get_filter_scheduler_algorithms_in_used(self, context=None):
        if context is None:
            context = context.get_admin_context()
    
        return self.manager.get_filter_scheduler_algorithms_in_used(context)

    def get_host_scheduler_algorithm_in_used(self, context=None):
        if context is None:
            context = context.get_admin_context()
    
        return self.manager.get_host_scheduler_algorithm_in_used(context)
    
    def get_vm_select_algorithm_in_used(self, context=None):
        if context is None:
            context = context.get_admin_context()
    
        return self.manager.get_vm_select_algorithm_in_used(context)
    
    """
    *****************
    * host_cpu_data *
    *****************
    """
    def get_all_host_cpu_data(self, context=None):
        if context is None:
            context = context.get_admin_context()
            
        return self.manager.get_all_host_cpu_data(context)
    
    def get_host_cpu_data_by_id(self, context=None, id):
        if context is None:
            context = context.get_admin_context()
    
        return self.manager.get_host_cpu_data_by_id(context, id)
    
    def create_host_cpu_data_temp_by_id(self, context=None, update_values, host_uuid):
        if context is None:
            context = context.get_admin_context()
    
        return self.manager.create_host_cpu_data_temp_by_id(context, update_values, host_uuid)
    
    def update_host_cpu_data_temp_by_id(self, context=None, update_values, host_uuid):
        if context is None:
            context = context.get_admin_context()
    
        return self.manager.update_host_cpu_data_temp_by_id(context, update_values, host_uuid)
    
    def get_host_cpu_data_temp_by_id(self, context=None, id):
        if context is None:
            context = context.get_admin_context()
    
        return self.manager.get_host_cpu_data_temp_by_id(context, id)
    
    def compute_host_cpu_mhz(self, context=None, host_uuid_temp):
        if context is None:
            context = context.get_admin_context()
        
        return self.hosts_rpcapi.compute_host_cpu_mhz(context, host_uuid_temp)
    
    
    
    """
    *****************
    * hosts_states *
    *****************
    """
    def get_all_hosts_states(self, context=None):
        if context is None:
            context = context.get_admin_context()
        
        return self.manager.get_all_hosts_states(context)
    
    def get_host_task_states_by_id(self, context=None, id):
        if context is None:
            context = context.get_admin_context()
        
        return self.manager.get_host_task_states_by_id(context, id)
            
    def delete_host_task_states_by_id(self, context=None, id):
        if context is None:
            context = context.get_admin_context()
        
        return self.manager.delete_host_task_states_by_id(context, id)
            
    def update_host_task_states(self, context=None, id, update_value):
        if context is None:
            context = context.get_admin_context()
        
        return self.manager.update_host_task_states(context, id, update_value)
            
    def get_all_hosts_task_states_sorted_list(self, context=None):
        if context is None:
            context = context.get_admin_context()
        
        return self.manager.get_all_hosts_task_states_sorted_list(context)     
    
    def get_host_running_states_by_id(self, context=None, id):
        if context is None:
            context = context.get_admin_context()
        
        return self.manager.get_host_running_states_by_id(context, id)
            
    def update_host_running_states(self, context=None, id, update_value):
        if context is None:
            context = context.get_admin_context()
        
        return self.manager.update_host_running_states(context, id, update_value)
            
    def delete_host_running_states_by_id(self, context=None, id):
        if context is None:
            context = context.get_admin_context()
        
        return self.manager.delete_host_running_states_by_id(context, id)
            
    def get_all_hosts_running_states_sorted_list(self, context=None):
        if context is None:
            context = context.get_admin_context()
        
        return self.manager.get_all_hosts_running_states_sorted_list(context)   
    
    def get_host_load_states_by_id(self, context=None, id):
        if context is None:
            context = context.get_admin_context()
        
        return self.manager.get_host_load_states_by_id(context, id)
            
    def update_host_load_states(self, context=None, id, update_value):
        if context is None:
            context = context.get_admin_context()
        
        return self.manager.update_host_load_states(context, id, update_value)
            
    def delete_host_load_states_by_id(self, context=None, id):
        if context is None:
            context = context.get_admin_context()
        
        return self.manager.delete_host_load_states_by_id(context, id)
            
    def get_all_hosts_load_states_sorted_list(self, context=None):
        if context is None:
            context = context.get_admin_context()
        
        return self.manager.get_all_hosts_load_states_sorted_list(context)
    
    
    
    """
    ******************
    * host_init_data *
    ******************
    """
    def create_host_init_data(self, context=None, update_values):
        if context is None:
            context = context.get_admin_context()
        
        return self.manager.create_host_init_data(context, update_values)
    
    def update_host_init_data(self, context=None, host_id, update_values):
        if context is None:
            context = context.get_admin_context()
        
        return self.manager.update_host_init_data(context, host_id, update_values)
    
    def get_host_init_data(self, context=None, host_id):
        if context is None:
            context = context.get_admin_context()
        
        return self.manager.get_host_init_data(context, host_id)
    
    def get_all_hosts_init_data(self, context=None):
        if context is None:
            context = context.get_admin_context()
        
        return self.manager.get_all_hosts_init_data(context)
    
    def create_host_init_data_temp(self, context=None, update_values):
        if context is None:
            context = context.get_admin_context()
        
        return self.manager.create_host_init_data_temp(context, update_values)
    
    def update_host_init_data_temp(self, context=None, host_id, update_values):
        if context is None:
            context = context.get_admin_context()
        
        return self.manager.update_host_init_data_temp(context, host_id, update_values)
    
    def get_host_init_data_temp(self, context=None, host_uuid_temp):
        if context is None:
            context = context.get_admin_context()
        
        return self.manager.get_host_init_data_temp(context, host_uuid_temp)
    
    
    
    """
    ***************
    * vm_cpu_data *
    ***************
    """
    def get_all_vms_cpu_data(self, context=None):
        if context is None:
            context = context.get_admin_context()
        
        return self.manager.get_all_vms_cpu_data(context)
            
    def get_vm_cpu_data_by_vm_id(self, context=None, vm_id):
        if context is None:
            context = context.get_admin_context()
        
        return self.manager.get_vm_cpu_data_by_vm_id(context, vm_id)
            
    def delete_vm_cpu_data_by_vm_id(self, context=None, vm_id):
        if context is None:
            context = context.get_admin_context()
        """
        注：验证指定的虚拟式实例是否存在，如果不存在，则验证其主机上存储的cpu数据是否存在，
        如果存在则删除其数据；
        """    
        try:
            vm_cpu_data = self.get_vm_cpu_data_by_vm_id(context, vm_id)
        except exception.NotFound:
            raise exc.HTTPNotFound()
        host_name = vm_cpu_data['host_name']
        return self.hosts_rpcapi.get_vm_cpu_data_by_vm_id(context, vm_id, host_name)
    
    def get_vm_cpu_data_by_host_id(self, context=None, host_id):
        if context is None:
            context = context.get_admin_context()
        
        return self.manager.get_vm_cpu_data_by_host_id(context, host_id)
    
    def delete_vm_cpu_data_by_host_id(self, context=None, host_id):
        if context is None:
            context = context.get_admin_context()
        
        return self.manager.delete_vm_cpu_data_by_host_id(context, host_id)
    
    
    
    """
    ****************
    * host_meminfo *
    ****************
    """
    def get_meminfo_by_id(self, context=None, id):
        if context is None:
            context = context.get_admin_context()
        
        return self.hosts_rpcapi.get_meminfo_by_id(context, id)
    
    
    """
    *******************
    * vms on host ram *
    *******************
    """
    def get_vms_ram_on_specific(self, context=None, vms_list, host_uuid):
        if context is None:
            context = context.get_admin_context()
        
        return self.hosts_rpcapi.get_meminfo_by_id(context, vms_list, host_uuid)
    
    
    
class HostToGlobalAPI(base.Base):
    """
    API for interacting with the host manager.
    """

    def __init__(self, **kwargs):
        self.hosts_global_rpcapi = hosts_rpcapi.HostToGlobalRPCAPI()
        super(HostToGlobalAPI, self).__init__(**kwargs)  
    
    """
    ********************
    * vm_host_miration *
    ********************
    """
    def vm_to_host_migrate(self, context=None, vm, host):
        vm_api = vms.API()
        
        if context is None:
            context = context.get_admin_context()
        
        vm_metadata = vm_api.get_vm_metadata_by_id(self, context, vm)
        orig_host = vm_metadata['host_id']
        dest_host = host
        
        return self.hosts_global_rpcapi.vm_to_host_migrate(context, vm, orig_host, dest_host)
    
    
    """
    **************
    * host_power *
    **************
    """
    def switch_host_off(self, context=None, sleep_command, host):
        if context is None:
            context = context.get_admin_context()
        
        return self.hosts_global_rpcapi.switch_host_off(context, sleep_command, host)
    
    def switch_host_on(self, context=None, ether_wake_interface, host_macs, host):
        if context is None:
            context = context.get_admin_context()
        
        return self.hosts_global_rpcapi.switch_host_on(context, 
                                               ether_wake_interface, 
                                               host_macs,
                                               host)