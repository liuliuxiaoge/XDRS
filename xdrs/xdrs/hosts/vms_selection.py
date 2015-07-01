import os
import libvirt
import numpy
from oslo.config import cfg
from xdrs import hosts

CONF = cfg.CONF
CONF.import_opt('local_data_directory', 'xdrs.service')
CONF.import_opt('network_migration_bandwidth', 'xdrs.service')
CONF.import_opt('vm_select_algorithm_path', 'xdrs.service')
CONF.import_opt('overload_algorithm_path', 'xdrs.service')
CONF.import_opt('host_cpu_usable_by_vms', 'xdrs.service')

def local_vms_select(context):         
    hosts_api = hosts.API()
    context = context.get_admin_context()
      
    vm_uuids_temp = _get_previous_vms(CONF.local_data_directory)
    host_path = CONF.local_data_directory
    
    vir_connection = libvirt.openReadOnly(None)
    vm_ram = _get_ram(vir_connection, vm_uuids_temp)
    
    migration_time = _calculate_migration_time(
                        vm_ram, 
                        float(CONF.network_migration_bandwidth)
                    )
    
    vm_select_algorithm = hosts_api.get_vm_select_algorithm_in_used(context)
    vm_select_algorithm_name = vm_select_algorithm['algorithm_name']
    vm_select_algorithm_params = vm_select_algorithm['algorithm_params']
    vm_select_algorithm_fuction = CONF.vm_select_algorithm_path + '.' + vm_select_algorithm_name
    vm_select_algorithm_fuction_params = [vm_select_algorithm_params,
                                         migration_time]
    
    overload_algorithm = hosts_api.get_overload_algorithm_in_used(context)
    overload_algorithm_name = overload_algorithm['algorithm_name']
    overload_algorithm_params = overload_algorithm['algorithm_params']
    overload_algorithm_fuction = CONF.overload_algorithm_path + '.' + overload_algorithm_name
    overload_algorithm_fuction_params = [overload_algorithm_params,
                                        migration_time]
    
    host_load_state_temp = 'overload'
    vm_mrigation_list = list()
        
    while host_load_state_temp == 'overload':
        host_cpu_mhz = _get_local_host_data(host_path)
        
        """
        注：可以从数据库中获取；
        """
        physical_cpu_mhz_total = int(_physical_cpu_mhz_total(vir_connection) *float(CONF.host_cpu_usable_by_vms))
        
        vms_uuid = vm_select_algorithm_fuction(vm_select_algorithm_fuction_params)
        del vm_uuids_temp[vms_uuid]
            
        host_cpu_utilization_temp = _vm_mhz_to_percentage(
                                        vm_uuids_temp,
                                        host_cpu_mhz,
                                        physical_cpu_mhz_total)
            
        host_load_state_temp, overload_detection_state = overload_algorithm_fuction(host_cpu_utilization_temp, 
                                                                overload_algorithm_fuction_params)
        vm_mrigation_list.add(vms_uuid)
        
    return vm_mrigation_list
            


def _get_previous_vms(path):
    """ 
    获取指定路径下的虚拟机UUID列表；
    """
    return os.listdir(path)

def _get_ram(vir_connection, vms):
    """ 
    为每一个UUID指定的虚拟机实例的获取其最大RAM值；
    """
    vms_ram = {}
    for uuid in vms:
        """
        通过libvirt获取分配给指定UUID的虚拟机实例的最大RAM值；
        """
        ram = _get_max_ram(vir_connection, uuid)
        if ram:
            vms_ram[uuid] = ram

    return vms_ram

def _get_max_ram(vir_connection, uuid):
    """ 
    通过libvirt获取分配给指定UUID的虚拟机实例的最大RAM值；
    """
    try:
        domain = vir_connection.lookupByUUIDString(uuid)
        return domain.maxMemory() / 1024
    except libvirt.libvirtError:
        return None
    
def _calculate_migration_time(vms, bandwidth):
    """ 
    根据虚拟机实例的RAM使用率数据计算虚拟机迁移的平均迁移时间；
    """
    return float(numpy.mean(vms.values()) / bandwidth)

def _vm_mhz_to_percentage(vm_mhz_history, host_mhz_history, physical_cpu_mhz):
    """ 
    转换虚拟机的CPU利用率到主机的CPU利用率；
    由历史虚拟机CPU利用率数据和历史主机CPU使用数据，共同来计算主机的CPU利用率百分比；
    
    vm_mhz_history：历史虚拟机CPU利用率列表，从本地读取虚拟机实例的采集数据（经过过滤）；
    host_mhz_history：历史主机CPU使用数据列表，从本地读取本地主机的采集数据；
    physical_cpu_mhz：所有可用的CPU核频率之和（MHz）；
    """
    max_len = max(len(x) for x in vm_mhz_history)
    if len(host_mhz_history) > max_len:
        host_mhz_history = host_mhz_history[-max_len:]
    print host_mhz_history
    
    mhz_history = [[0] * (max_len - len(x)) + x
                   for x in vm_mhz_history + [host_mhz_history]]
    return [float(sum(x)) / physical_cpu_mhz for x in zip(*mhz_history)]

def _get_local_host_data(path):
    """ 
    从本地存储路径读取本地主机的采集数据；
    """
    if not os.access(path, os.F_OK):
        return []
    with open(path, 'r') as f:
        result = [int(x) for x in f.read().strip().splitlines()]
    return result

def _physical_cpu_mhz_total(vir_connection):
    """ 
    通过libvirt获取所有CPU核频率之和（MHz）；
    """
    return _physical_cpu_count(vir_connection) * \
        _physical_cpu_mhz(vir_connection)
        
def _physical_cpu_count(vir_connection):
    """ 
    通过libvirt获取物理CPU的数目；
    """
    return vir_connection.getInfo()[2]

def _physical_cpu_mhz(vir_connection):
    """ 
    通过libvirt获取CPU频率（MHz）；
    """
    return vir_connection.getInfo()[3]