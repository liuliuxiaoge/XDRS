"""
实现选取合适的目标主机用于vms的迁移操作，特点是每次实现为一个vm选取迁移的目标主机，所以
采用此种流程的特点是更有利于集群的整体负载均衡，对应于多主机选取算法；
"""

import webob

from xdrs import hosts
from xdrs import exception
from oslo.config import cfg
import libvirt

CONF = cfg.CONF
CONF.import_opt('host_cpu_usable_by_vms', 'xdrs.service')
CONF.import_opt('overload_algorithm_path', 'xdrs.service')


def single_host_select(context, vms_list, host_uuid, hosts_list):
    """
    实现选取合适的目标主机用于vms的迁移操作，特点是每次实现为一个vm选取迁移的目标主机，所以
    采用此种流程的特点是更有利于集群的整体负载均衡，对应于多主机选取算法；
    参数：
    context：上下文环境信息；
    vms_list：所有要执行迁移操作的vm列表；
    hosts_list：经过前期过滤的所有被选主机列表；
    host_uuid：本地主机的uuid；
    输出：
    hosts_select，其格式为(vm1:host1,vm2:host2......)；
    """
    
    """
    1 遍历vms_list中的所有虚拟机实例，
      （1）访问数据库，获取每一个虚拟机实例的CPU使用数据；
           存储到vms_cpu_data中，其格式为(vm1:cpu_data1,vm2:cpu_data2......)；
      （2）获取每一个虚拟机实例的ram信息数据，存储到vms_ram_data；
    """
    hosts_api = hosts.API()
    
    vms_cpu_data = dict()
    vms_ram_data = dict()
    
        
    for vm in vms_list:
        try:
            cpu_data = hosts_api.get_vm_cpu_data_by_vm_id(context, vm)
        except exception.NotFound:
            raise webob.exc.HTTPNotFound()
        
        vms_cpu_data[vm] = cpu_data['cpu_data']
        
    try:
        vms_ram_data = hosts_api.get_vms_ram_on_specific(context, vms_list, host_uuid)
    except exception.VmsOnHostRamNotFoune:
        msg = _('vms on specific host ram data not found.')
        raise webob.exc.HTTPBadRequest(explanation=msg)
     
    """
    2 遍历hosts_list中的所有主机，
      （1）访问数据库，获取每一个主机的CPU使用数据；
           存储到hosts_cpu_data中，其格式为(host1:cpu_data1,host2:cpu_data2......)；
      （2）获取每一个主机的资源配额信息数据，存储到hosts_ram_space；
    """
    hosts_cpu_data = dict()
    hosts_total_ram = dict()
    hosts_free_ram = dict()
    for host in hosts_list:
        try:
            cpu_data = hosts_api.get_host_cpu_data_by_id(context, host)
        except exception.HostCpuDataNotFound:
            msg = _('host cpu data not found')
            raise webob.exc.HTTPBadRequest(explanation=msg)
        
        hosts_cpu_data[host] = cpu_data['cpu_data']
        
        try:
            host_meminfo = hosts_api.get_meminfo_by_id(context, host)
        except exception.HostMemroyInfoNotFound:
            msg = _('host memroy info not found')
            raise webob.exc.HTTPBadRequest(explanation=msg)
        
        hosts_total_ram[host] = host_meminfo['MemTotal']
        hosts_free_ram[host] = host_meminfo['MemFree']
    
    
    """
    3 循环遍历vms_list，针对其中的每一个vm，循环遍历hosts_list，为每一个host作虚拟机预迁移
      的CPU利用率计算，以判断虚拟机迁移到主机后，主机的运行状态为欠载还是过载；
      for i in vms_list
          for j in hosts_list
              (1) 判断hosts_free_ram[j]是否大于vms_ram_data[i]；
             （2）如果上述比较均满足条件，说明此主机资源足够此虚拟机迁移的需求；
                  应用hosts_cpu_data[j]和vms_cpu_data[i]，进行虚拟机预迁移的CPU利用率计算；
                  将计算的CPU利用率，赋值给vms_hosts_cpu[i][j]，格式为(cpu_data,state)；
          （1）针对一个vm，遍历完所有的host之后，遍历vms_hosts_cpu[i]，在state为正常的情况下，
               选取cpu_data值最小的主机，作为本vm的迁移目标主机；
               赋值到变量hosts_select，其格式为(vm1:host1,vm2:host2......)；
          （2）根据vm的ram的数据大小，改变选用的host的hosts_ram_space数据大小；
          （3）如果vms_hosts_cpu中的所有state均为过载状态，说明没有合适的vm迁移目标主机；
               赋值到变量hosts_select，令其值为None；
    """
    overload_algorithm = hosts_api.get_overload_algorithm_in_used(context)
    overload_algorithm_name = overload_algorithm['algorithm_name']
    overload_algorithm_params = overload_algorithm['algorithm_params']
    overload_algorithm_fuction = CONF.overload_algorithm_path + '.' + overload_algorithm_name
    overload_algorithm_fuction_params = [overload_algorithm_params]
    
    vm_hosts_cpu = dict()
    vms_hosts_mapper = dict()
    for vm in vms_list:
        for host in hosts_list:
            if hosts_free_ram[host] > vms_ram_data[vm]:
                vir_connection = libvirt.openReadOnly(host)
                physical_cpu_mhz_total = int(_physical_cpu_mhz_total(vir_connection) *
                                            float(CONF.host_cpu_usable_by_vms))
                
                host_cpu_utilization = _vm_mhz_to_percentage(
                    vms_cpu_data[vm],
                    hosts_cpu_data[host],
                    physical_cpu_mhz_total)
                
                overload, overload_detection_state = overload_algorithm_fuction(host_cpu_utilization, 
                                                                   overload_algorithm_fuction_params)
                
                vm_hosts_cpu[host] = (host_cpu_utilization, overload)
        
        count_num = 0
        cpu_data = 100.0
        for host_uuid, cpu_utilization in vm_hosts_cpu:
            host_cpu_utilization = cpu_utilization[0]
            host_load_state = cpu_utilization[1]
            
            if host_load_state == 'normalload':
                if host_cpu_utilization < cpu_data:
                    count_num = host_uuid
        
        vms_hosts_mapper[vm] = count_num
        
        hosts_free_ram[count_num] = hosts_free_ram[count_num] - vms_ram_data[vm]
        
        try:
            host_cpu_data_temp = hosts_api.update_host_cpu_data_temp_by_id(
                           context, 
                           hosts_free_ram[count_num], 
                           count_num)
        except exception.HostCpuDataNotFound:
            msg = _('host cpu data not found')
            raise webob.exc.HTTPBadRequest(explanation=msg)    
               
                
    
    """
    4 得到字典vms_hosts_mapper，其格式为(vm1:host1,vm2:host2......)；
    5 从vms_hosts_mapper中获取成功选取主机的虚拟机列表hosts_select_finally；
      从vms_hosts_mapper中获取没有选取到合适主机的虚拟机列表vm_noselect_list_finally；
    """
    vms_hosts_mapper_success = vms_hosts_mapper
    vms_hosts_mapper_fales = vms_hosts_mapper
    for vm, uuid in vms_hosts_mapper:
        if uuid == 0:
            del vms_hosts_mapper_success[vm]
        if uuid != 0:
            del vms_hosts_mapper_fales[vm]
    
    return vms_hosts_mapper_success, vms_hosts_mapper_fales



def _physical_cpu_mhz_total(vir_connection):
    """ 
    通过libvirt获取所有CPU核频率之和（MHz）；
    vir_connection：到libvirt的连接；
    """
    return _physical_cpu_count(vir_connection) * \
        _physical_cpu_mhz(vir_connection)
        
def _physical_cpu_count(vir_connection):
    """ 
    通过libvirt获取物理CPU的数目；
    vir_connection：到libvirt的连接；
    """
    return vir_connection.getInfo()[2]

def _physical_cpu_mhz(vir_connection):
    """ 
    通过libvirt获取CPU频率（MHz）；
    vir_connection：到libvirt的连接；
    """
    return vir_connection.getInfo()[3]

def _vm_mhz_to_percentage(vm_mhz_history, host_mhz_history, physical_cpu_mhz):
    """ 
    转换虚拟机的CPU利用率到主机的CPU利用率；
    由历史虚拟机CPU利用率数据和历史主机CPU使用数据，共同来计算主机的CPU利用率百分比；
    参数：
    vm_mhz_history：历史虚拟机CPU利用率列表，从本地读取虚拟机实例的采集数据（经过过滤）；
    host_mhz_history：历史主机CPU使用数据列表，从本地读取本地主机的采集数据；
    physical_cpu_mhz：所有可用的CPU核频率之和（MHz）；
    """
    max_len = max(len(x) for x in vm_mhz_history)
    if len(host_mhz_history) > max_len:
        host_mhz_history = host_mhz_history[-max_len:]
    
    mhz_history = [[0] * (max_len - len(x)) + x
                   for x in vm_mhz_history + [host_mhz_history]]
    return [float(sum(x)) / physical_cpu_mhz for x in zip(*mhz_history)]