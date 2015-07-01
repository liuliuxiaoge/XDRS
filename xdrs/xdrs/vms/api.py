import functools
from oslo.config import cfg
from xdrs.vms import rpcapi as vms_rpcapi
from xdrs.vms import manager as manager
from xdrs.db import base
from xdrs import exception
from xdrs.openstack.common import log as logging
from xdrs import rpc
import xdrs

LOG = logging.getLogger(__name__)

get_notifier = functools.partial(rpc.get_notifier, service='compute')
wrap_exception = functools.partial(exception.wrap_exception,
                                   get_notifier=get_notifier)
CONF = cfg.CONF
MAX_USERDATA_SIZE = 65535
RO_SECURITY_GROUPS = ['default']
VIDEO_RAM = 'hw_video:ram_max_mb'


def check_instance_state(vm_state=None, task_state=(None,),
                         must_have_launched=True):
    """
    Decorator to check VM and/or task state before entry to API functions.

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
        self.vms_rpcapi = vms_rpcapi.VmRPCAPI()
        self.manager = manager.VmManager()
        self.notifier = rpc.get_notifier('vms', CONF.vm)

        super(API, self).__init__(**kwargs)
    
    
    """
    ****************
    * vms_metadata *
    ****************
    """
    def get_all_vms_metadata(self, context=None):
        if context is None:
            context = context.get_admin_context()
        
        return self.manager.get_all_vms_metadata(context)
    
    def get_vm_metadata_by_id(self, context=None, id):
        if context is None:
            context = context.get_admin_context()
        
        return self.manager.get_vm_metadata_by_id(context, id)
    
    def get_vm_task_state_by_id(self, context=None, id):
        if context is None:
            context = context.get_admin_context()
        
        return self.manager.get_vm_task_state_by_id(context, id)
    
    def delete_vm_metadata_by_id(self, context=None, id):
        """
        注：这个方法需要比较细致地来写；
        注：检测相应主机上的虚拟机实例是否存在，如果存在，则提示不能删除此虚拟机
        的元数据信息；这里具体需要通过vms.rpcapi-vms.manager来实现；
        """
        if context is None:
            context = context.get_admin_context()
        
        return self.vms_rpcapi.delete_vm_metadata_by_id(context, id)
    
    
    
    
    """
    ***********************
    * vm_migration_record *
    ***********************
    """
    def get_all_vms_migration_records(self, context=None):
        if context is None:
            context = context.get_admin_context()
        
        return self.manager.get_all_vms_migration_records(context)
            
    def get_vm_migration_record_by_id(self, context=None, id):
        if context is None:
            context = context.get_admin_context()
        
        return self.manager.get_vm_migration_record_by_id(context, id)
            
    def create_vm_migration_record(self, context=None, vm_migration_record):
        if context is None:
            context = context.get_admin_context()
        
        return self.manager.create_vm_migration_record(context, vm_migration_record)
            
    def delete_vm_migration_record_by_id(self, context=None, id):
        if context is None:
            context = context.get_admin_context()
        
        return self.manager.delete_vm_migration_record_by_id(context, id)
            
    def get_specific_vm_migration_task_state(self, context=None, id):
        if context is None:
            context = context.get_admin_context()
        
        return self.manager.get_specific_vm_migration_task_state(context, id)
            
    def get_specific_vm_all_migration_records(self, context=None, id):
        if context is None:
            context = context.get_admin_context()
            
        return self.manager.get_specific_vm_all_migration_records(context, id)
            
    def get_specific_host_all_migration_records(self, context=None, id):
        if context is None:
            context = context.get_admin_context()
        
        return self.manager.get_specific_host_all_migration_records(context, id)
            
    def get_specific_host_all_migration_in_records(self, context=None, id):
        if context is None:
            context = context.get_admin_context()
        
        return self.manager.get_specific_host_all_migration_in_records(context, id)
            
    def get_specific_host_all_migration_out_records(self, context=None, id):
        if context is None:
            context = context.get_admin_context()
        
        return self.manager.get_specific_host_all_migration_out_records(context, id)
