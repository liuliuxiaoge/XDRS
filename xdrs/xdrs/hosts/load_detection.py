"""
主机欠载过载检测的实现（供守护进程调用的）；
"""
"""
本地管理进程将会以守护进程的形式运行在后台，并每间隔local_manager_interval
时间实现检测若干虚拟机实例是否应该被迁移到其他主机。每一次调用，本地管理进程
都会实现与以下步骤：
1.从<local_data_directory>/vm路径下读取虚拟机实例的资源使用数据；
2.调用algorithm_underload_detection配置选项制定的函数，实现判断本地主机是过载或者
  欠载；
3.如果本地主机是欠载的，发送请求到global manager的REST API，传递运行在本地主机上的
  所有的虚拟机实例的UUID列表参数vm_uuids；
4.如果本地主机不是欠载的，则调用在algorithm_overload_detection配置选项中指定的
  过载检测算法，实现对本地主机的过载检测；
5.如果本地主机是过载的，则调用在algorithm_vm_selection配置选项中制定的虚拟机实例
  选取算法，实现选取要执行迁移的虚拟机实例；
6.如果本地主机是过载的，则发送请求到全局管理服务（global manager）的REST API，通过
  参数vm_uuids传递通过虚拟机实例选取算法而选取的要进行迁移的虚拟机实例列表；
7.在local_manager_interval时间后，进行下一个进程的调用执行；
"""

import webob

import os
import time
import libvirt
import json
import numpy
from random import random
from oslo.config import cfg
from xdrs import hosts
from xdrs.daemon import Daemon
from xdrs import exception
from xdrs.compute.nova import novaclient

CONF = cfg.CONF
CONF.import_opt('local_data_directory', 'xdrs.service')
CONF.import_opt('host_cpu_usable_by_vms', 'xdrs.service')
CONF.import_opt('network_migration_bandwidth', 'xdrs.service')
CONF.import_opt('underload_algorithm_path', 'xdrs.service')
CONF.import_opt('overload_algorithm_path', 'xdrs.service')
CONF.import_opt('vm_select_algorithm_path', 'xdrs.service')
CONF.import_opt('filter_scheduler_algorithm_path', 'xdrs.service')

"""
注：这里放到/xdrs/api/load_detection.py中，作为一个负载检测的API；
"""
class HostLoadDetection(Daemon):
    def __init__(self, conf):
        self.conf = conf
        """
        注：在这里会把运行参数写在同一个配置文件中；
        """
        self.interval = int(conf.get('interval', 1800))

    def run_forever(self, *args, **kwargs):
        reported = time.time()
        time.sleep(random() * self.interval)
        while True:
            begin = time()
            local_load_detect(reported)
            elapsed = time() - begin
            if elapsed < self.interval:
                time.sleep(self.interval - elapsed)

    def run_once(self, *args, **kwargs):
        begin = reported = time.time()
        local_load_detect(reported)
        elapsed = time.time() - begin
    
    def load_detect(self):
        return
    

def init_state(config):
    """ 
    Initialize a dict for storing the state of the local manager.

    :param config: A config dictionary.
     :type config: dict(str: *)

    :return: A dictionary containing the initial state of the local manager.
     :rtype: dict
    """
    vir_connection = libvirt.openReadOnly(None)
    if vir_connection is None:
        message = 'Failed to open a connection to the hypervisor'
        raise OSError(message)

    """
    physical_cpu_mhz_total：通过libvirt获取所有CPU核频率之和（MHz）；
    host_cpu_usable_by_vms：主机中可以分配给虚拟机使用的cpu个数占总体cpu的百分比（阈值）；
    """
    physical_cpu_mhz_total = int(
        _physical_cpu_mhz_total(vir_connection) *
        float(CONF.host_cpu_usable_by_vms))
    
    return {'previous_time': 0.,
            'vir_connection': vir_connection,
            'db': init_db(config['sql_connection']),
            'physical_cpu_mhz_total': physical_cpu_mhz_total,
            'hostname': vir_connection.getHostname(),
            'hashed_username': sha1(config['os_admin_user']).hexdigest(),
            'hashed_password': sha1(config['os_admin_password']).hexdigest()}


def local_load_detect(context):
           
    hosts_api = hosts.API()
    context = context.get_admin_context()
    """
    1.确定存储本地虚拟机数据的路径；
    """
    vm_path = _build_local_vm_path(CONF.local_data_directory)
    
    """
    2.从本地存储文件读取虚拟机实例的采集数据；
    """
    vm_cpu_mhz = _get_local_vm_data(vm_path)
    
    """
    3.为每一个UUID指定的虚拟机实例的获取其最大RAM值；
    """
    vir_connection = libvirt.openReadOnly(None)
    vm_ram = _get_ram(vir_connection, vm_cpu_mhz.keys())
    
    """
    4.删除在UUID列表中没有出现的虚拟机实例的记录信息；
    """
    vm_cpu_mhz = _cleanup_vm_data(vm_cpu_mhz, vm_ram.keys())
    
    """
    5.如果没有获取到vm_cpu_mhz数据，说明当前的主机是处于闲置状态，
      即其上没有虚拟机实例在运行，所以直接返回；
    """
    if not vm_cpu_mhz:
        return False
    
    """    
    6.确定存储本地本地主机数据的路径；
    """
    host_path = _build_local_host_path(CONF.local_data_directory)
    
    """
    7.从本地存储路径读取本地主机的采集数据；
    """
    host_cpu_mhz = _get_local_host_data(host_path)
    
    """
    8.由历史虚拟机CPU利用率数据和历史主机CPU使用数据，共同来计算主机的CPU利用率百分比；
      @@@@注：这里需要重点看一下，虚拟机CPU利用率和主机CPU利用率的关系；
    """
    """
    physical_cpu_mhz_total为常数，所有可用的CPU核频率之和（MHz）；
    _physical_cpu_mhz_total：通过libvirt获取所有CPU核频率之和（MHz）（CPU数目*单个CPU频率）；
    host_cpu_usable_by_vms：主机中可以分配给虚拟机使用的cpu个数占总体cpu的百分比（阈值）；
    """
    physical_cpu_mhz_total = int(
        _physical_cpu_mhz_total(vir_connection) *
        float(CONF.host_cpu_usable_by_vms))
    
    """
    vm_cpu_mhz：从本地读取虚拟机实例的采集数据（经过过滤）；
    host_cpu_mhz：从本地读取本地主机的采集数据；
    physical_cpu_mhz_total：所有可用的CPU核频率之和（MHz）；
    """
    host_cpu_utilization = _vm_mhz_to_percentage(
        vm_cpu_mhz.values(),
        host_cpu_mhz,
        physical_cpu_mhz_total)
    
    if not host_cpu_utilization:
        return False
    
    
    """
    9.根据虚拟机实例的RAM使用率数据和配置文件中定义的虚拟机实例迁移所允许的网络带宽
      来计算虚拟机迁移的平均迁移时间；
      network_migration_bandwidth：虚拟机实例迁移所允许的网络带宽（这里定义为10MB）；
      @@@@注：这里计算的是所有虚拟机实例中每一个虚拟机实例平均的迁移时间；
    """
    migration_time = _calculate_migration_time(
                        vm_ram, 
                        float(CONF.network_migration_bandwidth)
                    )
    
    """
    10.确定用于进行主机欠载检测的算法及其参数；
    （1）从配置文件解析算法参数；
    （2）从配置参数读取配置选项，确定本地主机的欠载检测算法；
    注：读取数据库获取算法名称和算法配置参数；
    所实现的四种简单的欠载检测算法中，time_step和migration_time是没有用处的；
    """ 
    underload_algorithm = hosts_api.get_underload_algorithm_in_used(context)
    underload_algorithm_name = underload_algorithm['algorithm_name']
    underload_algorithm_params = underload_algorithm['algorithm_params']
    underload_algorithm_fuction = CONF.underload_algorithm_path + '.' + underload_algorithm_name
    underload_algorithm_fuction_params = [underload_algorithm_params,
                                         migration_time]
    
    """
    11.确定用于进行主机过载检测的算法及其参数；
    （1）从配置文件解析算法参数；
    （2）从配置参数读取配置选项，确定本地主机的过载检测算法；
    注：读取数据库获取算法名称和算法配置参数；
    所实现的三种简单的过载检测算法中，time_step和migration_time是没有用处的；
    主要应用于较为复杂的过载检测算法；
    具体参数应该拿到具体的算法中进行解析；
    """  
    overload_algorithm = hosts_api.get_overload_algorithm_in_used(context)
    overload_algorithm_name = overload_algorithm['algorithm_name']
    overload_algorithm_params = overload_algorithm['algorithm_params']
    overload_algorithm_fuction = CONF.overload_algorithm_path + '.' + overload_algorithm_name
    overload_algorithm_fuction_params = [overload_algorithm_params,
                                        migration_time]
    
    """
    13.调用确定的欠载检测算法进行本地主机的欠载检测；
    """
    underload, underload_detection_state = underload_algorithm_fuction(host_cpu_utilization, 
                                                                      underload_algorithm_fuction_params)
    
    """ 
    14.调用确定的过载检测算法进行本地主机的过载检测；
    """
    overload, overload_detection_state = overload_algorithm_fuction(host_cpu_utilization, 
                                                                   overload_algorithm_fuction_params)
    
    
    """
    @@@@从HostInitData获取本地主机的uuid；
    """
    host_id = ''
    
    if underload:
        host_load_state = 'underload'
    if overload:
        host_load_state = 'overload'
    else:
        host_load_state = 'normalload'
        
    """
    更新数据表HostLoadState中的负载状态信息；
    """
    try:
        host_load_state = hosts_api.update_host_load_states(context, host_id, host_load_state)
    except exception.HostLoadStateNotFound as ex:
        raise webob.exc.HTTPNotFound(explanation=ex.format_message())
    
    return 0



def _build_local_vm_path(local_data_directory):
    """ 
    建立存储本地虚拟机数据的路径；
    """
    return os.path.join(local_data_directory, 'vms')

def _get_local_vm_data(path):
    """ 
    从本地存储文件读取虚拟机实例的采集数据；
    """
    result = {}
    for uuid in os.listdir(path):
        with open(os.path.join(path, uuid), 'r') as f:
            result[uuid] = [int(x) for x in f.read().strip().splitlines()]
    return result

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

def _cleanup_vm_data(vm_data, uuids):
    """ 
    删除在UUID列表中没有出现的虚拟机实例的记录信息；
    """
    for uuid, _ in vm_data.items():
        if uuid not in uuids:
            del vm_data[uuid]
    return vm_data

def _build_local_host_path(local_data_directory):
    """ 
    建立存储本地本地主机数据的路径；
    """
    return os.path.join(local_data_directory, 'host')

def _get_local_host_data(path):
    """ 
    从本地存储路径读取本地主机的采集数据；
    """
    if not os.access(path, os.F_OK):
        return []
    with open(path, 'r') as f:
        result = [int(x) for x in f.read().strip().splitlines()]
    return result

def _vm_mhz_to_percentage(vm_mhz_history, host_mhz_history, physical_cpu_mhz):
    """ 
    转换虚拟机的CPU利用率到主机的CPU利用率；
    由历史虚拟机CPU利用率数据和历史主机CPU使用数据，共同来计算主机的CPU利用率百分比；


    vm_mhz_history：历史虚拟机CPU利用率列表，从本地读取虚拟机实例的采集数据（经过过滤）；
    host_mhz_history：历史主机CPU使用数据列表，从本地读取本地主机的采集数据；
    physical_cpu_mhz：所有可用的CPU核频率之和（MHz）；

    :return: The history of the host's CPU utilization in percentages.
     :rtype: list(float)
    """
    max_len = max(len(x) for x in vm_mhz_history)
    if len(host_mhz_history) > max_len:
        host_mhz_history = host_mhz_history[-max_len:]
    print host_mhz_history
    
    """
    vm_mhz_history = [[0, 1, 2, 3, 4], [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [0, 1, 2, 3, 4, 5, 6], [0, 1, 2, 3, 4, 5]]
    host_mhz_history = [111,121,131,141,151,161,171,181,191,201,211,221,231]
    physical_cpu_mhz = 56000
    
    host_mhz_history = 
    [141, 151, 161, 171, 181, 191, 201, 211, 221, 231]
    
    test5 = [len(x) for x in vm_mhz_history]
    print test5
    [5, 10, 7, 6]
    
    test4 = [[0] * len(x) for x in vm_mhz_history]
    print test4
    [[0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0]]
    
    test3 = [[0] * (max_len - len(x)) for x in vm_mhz_history]
    print test3
    [[0, 0, 0, 0, 0], [], [0, 0, 0], [0, 0, 0, 0]]
    
    test2 = [[0] * (max_len - len(x)) + x for x in vm_mhz_history]
    print test2
    [[0, 0, 0, 0, 0, 0, 1, 2, 3, 4], [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [0, 0, 0, 0, 1, 2, 3, 4, 5, 6], [0, 0, 0, 0, 0, 1, 2, 3, 4, 5]]
    
    mhz_history = [[0] * (max_len - len(x)) + x for x in vm_mhz_history + [host_mhz_history]]
    print mhz_history
    [
     [0, 0, 0, 0, 0, 0, 1, 2, 3, 4], 
     [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], 
     [0, 0, 0, 0, 1, 2, 3, 4, 5, 6], 
     [0, 0, 0, 0, 0, 1, 2, 3, 4, 5], 
     [141, 151, 161, 171, 181, 191, 201, 211, 221, 231]
    ]
    
    test10 = zip(*mhz_history)
    print test10
    [
     (0, 0, 0, 0, 141), 
     (0, 1, 0, 0, 151), 
     (0, 2, 0, 0, 161), 
     (0, 3, 0, 0, 171),
     (0, 4, 1, 0, 181),
     (0, 5, 2, 1, 191),
     (1, 6, 3, 2, 201),
     (2, 7, 4, 3, 211),
     (3, 8, 5, 4, 221),
     (4, 9, 6, 5, 231)
    ]
    
    test7 = [x for x in zip(*mhz_history)]
    print test7
    [
    (0, 0, 0, 0, 141), 
    (0, 1, 0, 0, 151), 
    (0, 2, 0, 0, 161), 
    (0, 3, 0, 0, 171),
    (0, 4, 1, 0, 181),
    (0, 5, 2, 1, 191),
    (1, 6, 3, 2, 201),
    (2, 7, 4, 3, 211),
    (3, 8, 5, 4, 221),
    (4, 9, 6, 5, 231)
    ]
    
    test8 = [float(sum(x)) for x in zip(*mhz_history)]
    print test8
    [141.0, 152.0, 163.0, 174.0, 186.0, 199.0, 213.0, 227.0, 241.0, 255.0]
    
    test9 = [float(sum(x)) / physical_cpu_mhz for x in zip(*mhz_history)]
    print test9
    [0.002517857142857143, 0.0027142857142857142, 0.0029107142857142856, 0.003107142857142857, 0.0033214285714285715, 0.0035535714285714285, 0.0038035714285714287, 0.004053571428571429, 0.004303571428571428, 0.0045535714285714285]
    """
    mhz_history = [[0] * (max_len - len(x)) + x
                   for x in vm_mhz_history + [host_mhz_history]]
    return [float(sum(x)) / physical_cpu_mhz for x in zip(*mhz_history)]

def _calculate_migration_time(vms, bandwidth):
    """ 
    根据虚拟机实例的RAM使用率数据计算虚拟机迁移的平均迁移时间；
    """
    return float(numpy.mean(vms.values()) / bandwidth)

def _parse_parameters(params):
    """ 
    Parse algorithm parameters from the config file.
    从配置文件解析算法参数；

    :param params: JSON encoded parameters.
     :type params: str

    :return: A dict of parameters.
     :rtype: dict(str: *)
    """
    return dict((str(k), v)
                for k, v in json.loads(params).items())

def _call_function_by_name(name, args):
    """ 
    Call a function specified by a fully qualified name.
    """
    fragments = name.split('.')
    module = '.'.join(fragments[:-1])
    fromlist = fragments[-2]
    function = fragments[-1]
    m = __import__(module, fromlist=fromlist)
    return getattr(m, function)(*args)

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

def _get_all_available_hosts(context):
    hosts_api = hosts.API()
    hosts = novaclient(context).hosts.index()
    hosts_states = hosts_api.get_all_hosts_load_states_sorted_list(context)
    hosts_temp = list()
    
    for uuid, host_load_state in hosts_states:
        if host_load_state == 'normalload':
            hosts_temp.add(uuid)
            
    for i in hosts_temp:
        if i not in hosts['id']:
            del hosts_temp[i]
            
    available_hosts = hosts_temp
    
    return available_hosts

def _get_filter_scheduler_algorithms_in_use(context):
    hosts_api = hosts.API()
    filter_scheduler_algorithms_fuctions = list()
    
    filter_scheduler_algorithms_names = hosts_api.get_filter_scheduler_algorithms_in_used(context)
    
    for algorithm_name in filter_scheduler_algorithms_names:
        algorithm_fuction = CONF.filter_scheduler_algorithm_path + '.' + algorithm_name
        filter_scheduler_algorithms_fuctions.add(algorithm_fuction)
        
    return filter_scheduler_algorithms_fuctions

def _get_filter_hosts(host_list, filter_scheduler_algorithms_fuctions):
        for algorithm_fuction in filter_scheduler_algorithms_fuctions:
            host_list = filter_scheduler_algorithms_fuctions(host_list)
            
def _vm_to_host_migrate(context, vm_host_mapper):
    host_to_global_api = hosts.HostToGlobalAPI()
    migration_states = list()
    
    for vm, host in vm_host_mapper:
        state = host_to_global_api.vm_to_host_migrate(context, vm, host)
        migration_states.add(state)
    
    return migration_states

def _switch_host_off(context, sleep_command, host):
    host_to_global_api = hosts.HostToGlobalAPI()
    return host_to_global_api.switch_host_off(context, sleep_command, host)

def _switch_host_on(self, context, ether_wake_interface, host_macs, host):
    host_to_global_api = hosts.HostToGlobalAPI()
    return host_to_global_api.switch_host_on(context, ether_wake_interface, host_macs. host)