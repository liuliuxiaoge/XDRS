"""
本地主机数据采集的实现（供守护进程调用的）；
"""
"""
数据采集服务将作为一个LINUX守护进程运行在后台，将会在每间隔data_collector_interval
时间采集一次虚拟机实例的数据，当虚拟机实例数据采集方法被调用，该组件将会执行以下步骤：
1.获取上一次采集数据时，运行在本地主机上的虚拟机实例列表；
2.访问Nova API实现获取当前运行在本地主机上的虚拟机实例列表；
3.通过比较新旧虚拟机实例列表来确定最新添加或者删除的虚拟机实例列表；
4.更新<local_data_directory>/vm路径下的文件，实现删除那些最新删除的虚拟机实例
  所对应的文件；
  注：采集的虚拟机实例的CPU利用率数据存储在本地主机的指定路径下，每个文件对应于
      一个虚拟机实例，文件以虚拟机实例的UUID来进行命名。
5.为每个新添加的虚拟机实例从中央数据库获取data_collector_data_length值；
6.调用Libvirt API来获取运行在本地主机上的每个虚拟机实例的CPU信息；
7.根据本地主机的频率和上一次获取数据的时间间隔情况，转换通过Libvirt API获取的
  虚拟机实例的CPU数据为平均的CPU利用率数据（MHZ）；
  注：这里是一个重点需要研究的地方，分析源码看看是怎么实现的；
8.存储转换后的数据到<local_data_directory>/vm路径下对应的文件中，并提交数据到
  中央数据库中；
9.在间隔data_collector_interval时间后，调用下一个本地数据采集的执行过程；
  注：这由上一层次实现；
"""

import webob

from collections import deque
import os
import time
import libvirt
from random import random
from oslo.config import cfg
from xdrs import hosts
from xdrs import exception

from xdrs.daemon import Daemon

CONF = cfg.CONF
CONF.import_opt('local_data_directory', 'xdrs.service')
CONF.import_opt('data_collector_data_length', 'xdrs.service')
CONF.import_opt('host_cpu_overload_threshold', 'xdrs.service')
CONF.import_opt('host_cpu_usable_by_vms', 'xdrs.service')

"""
注：这里放到/xdrs/api/data_collector.py中，作为一个数据采集的API；
"""
class DataCollection(Daemon):
    def __init__(self, conf):
        self.conf = conf
        """
        注：在这里会把运行参数写在同一个配置文件中；
        """
        self.interval = int(conf.get('interval', 1800))

    def run_forever(self, *args, **kwargs):
        reported = time.time()
        time.sleep(random() * self.interval)
        init_state()
        while True:
            begin = time()
            local_data_collector(reported)
            elapsed = time() - begin
            if elapsed < self.interval:
                time.sleep(self.interval - elapsed)

    def run_once(self, *args, **kwargs):
        begin = reported = time.time()
        init_state()
        local_data_collector(reported)
        elapsed = time.time() - begin
    
    def load_detect(self):
        return


def init_state():
    """ 
    Initialize a dict for storing the state of the data collector.
    """
    """
    @@@@注：这里可以放在xdrs-host的初始化过程中来实现，并写入数据表HostInitData；
    这里的操作就是对这个数据表进行数据的初始化操作；
    其实这个系统有个瓶颈，就是若干数据库访问量过大，根据云平台集群规模和所建立的
    虚拟机数量的大小，可能同时会有大量的数据表更新等操作访问数据库。
    db.update_host(hostname,
                   int(host_cpu_mhz * host_cpu_usable_by_vms),
                   physical_cpus,
                   host_ram)
    """
    hosts_api = hosts.API()
    
    vir_connection = libvirt.openReadOnly(None)
    hostname = vir_connection.getHostname()
    """
    获取本地主机总的CPU MHZ和RAM数据；
    """
    host_cpu_mhz, host_ram = get_host_characteristics(vir_connection)
    """
    通过libvirt获取物理CPU的数目；
    """
    physical_cpus = physical_cpu_count(vir_connection)
    
    """
    主机中可以分配给虚拟机使用的cpu个数占总体cpu的百分比（阈值）；
    """
    host_cpu_usable_by_vms = float(CONF.host_cpu_usable_by_vms)
    local_cpu_mhz = int(host_cpu_mhz * host_cpu_usable_by_vms)
    host_cpu_overload_threshold = float(CONF.host_cpu_overload_threshold) * \
                                host_cpu_usable_by_vms
    physical_core_mhz = host_cpu_mhz / physical_cpus
    host_id = 2
    """在系统初始化的过程中随机生成；"""
    
    init_data = {'host_name': hostname,
                 'host_id': host_id,
                 'local_cpu_mhz': local_cpu_mhz,
                 'physical_cpus': physical_cpus,
                 'host_ram': host_ram,
                 'previous_time': 0.,
                 'previous_cpu_time': dict(),
                 'previous_cpu_mhz': dict(),
                 'previous_host_cpu_time_total': 0.,
                 'previous_host_cpu_time_busy': 0.,
                 'previous_overload': -1,
                 'host_cpu_overload_threshold': host_cpu_overload_threshold,
                 'physical_cpu_mhz': host_cpu_mhz,
                 'physical_core_mhz': physical_core_mhz
                 }
    
    try:
        host_init_data = hosts_api.create_host_init_data(init_data)
    except exception.HostInitDataNotFound:
        msg = _('host init data not found')
        raise webob.exc.HTTPBadRequest(explanation=msg)
    """
    注：这里稍后要做改进，设置一个数据表HostInitData，这里的操作就是对这个数据表
    进行数据的初始化操作；
    其实这个系统有个瓶颈，就是若干数据库访问量过大，根据云平台集群规模和所建立的
    虚拟机数量的大小，可能同时会有大量的数据表更新等操作访问数据库。
    db.update_host(hostname,
                   int(host_cpu_mhz * host_cpu_usable_by_vms),
                   physical_cpus,
                   host_ram)
    """
    

def local_data_collector(context):
    """
    注：基本不用大改（除了注的部分），需要对具体算法进行理解总结；
    """
    
    """
    @@@@注：通过主机名获取HOST UUID；
    UUID在组件初始化的过程中实现随机生成；
    """
    host_id = 2;
    hosts_api = hosts.API()
    
    try:
        init_data = hosts_api.get_host_init_data(host_id)
    except exception.HostInitDataNotFound:
        msg = _('host init data not found')
        raise webob.exc.HTTPBadRequest(explanation=msg)
    
    """
    1.建立存储本地db.select_cpu_mhz_for_vm虚拟机数据和本地主机数据的路径；
    注：data_collector_data_length：存储在本地的最新的数据数量；
    local_data_directory="/var/lib/xdrs"
    data_collector_data_length=100
    """
    vm_path = _build_local_vm_path(CONF.local_data_directory)
    host_path = _build_local_host_path(CONF.local_data_directory)
    data_length = int(CONF.data_collector_data_length)
    
    
    """
    2.获取指定路径下的虚拟机UUID列表；
    """
    vms_previous = _get_previous_vms(vm_path)
    
    """
    3.通过libvirt获取本地主机的VM的UUID数据统计信息；
    """
    vir_connection = libvirt.openReadOnly(None)
    vms_current = _get_current_vms(vir_connection)
    
    """
    4.通过比较新旧列表来确定新添加的虚拟机实例列表；
    """
    vms_added = _get_added_vms(vms_previous, vms_current.keys())
    added_vm_data = dict()
    
    """
    5.如果本地主机有新添加的虚拟机实例；
    从中央数据库获取新添加虚拟机实例之前的数据采集信息，
    因为有可能是迁移过来的虚拟机实例；
    （1）从中央数据库获取新添加虚拟机实例之前的数据采集信息，
         因为有可能是迁移过来的虚拟机实例； 
    （2）保存从中央数据库获取的新添加虚拟机实例的数据到本地存储文件；
    """
    if vms_added:
        for i, vm in enumerate(vms_added):
            if vms_current[vm] != libvirt.VIR_DOMAIN_RUNNING:
                del vms_added[i]
                del vms_current[vm]
        _create_new_vms_files(vms_added, vm_path)
        added_vm_data = _fetch_remote_data(data_length, vms_added)
        _write_vm_data_locally(vm_path, added_vm_data, data_length)
    
    """
    6.通过比较新旧列表来确定最新删除的虚拟机实例的列表；
    """
    vms_removed = _get_removed_vms(vms_previous, vms_current.keys())
    
    """  
    7.如果存在最新删除的虚拟机实例；
      清除对应于已经删除的虚拟机实例的保存在本地的数据信息；
      同时清除在初始化过程中的相关虚拟机实例的数据信息（这里后续关注数据初始化方法的实现）；
    """
    if vms_removed:
        _cleanup_local_vm_data(vm_path, vms_removed)
        """
        注：这里有待探讨，我认为应该加上在数据库中删除所有的vm的init_data数据表信息；
        """
        for vm in vms_removed:
            del init_data['previous_cpu_time'][vm]
            del init_data['previous_cpu_mhz'][vm]
    
    """
    8.开始进行数据采集的正式操作；
    """
    current_time = time.time()
    
    """
    9.获取虚拟机实例的平均CPU利用率数据（MHz）；
    注：这里是一个重点，需要好好分析；
    vir_connection：到libvirt的连接；
    physical_core_mhz：每个物理CPU core的频率（MHz）；
    本地主机总的CPU MHZ频率除以物理CPU的个数；
    previous_cpu_time：上一次的虚拟机的CPU时间；
    previous_time：上一次的时间戳；
    current_time：当前的时间戳；
    current_vms：当前的虚拟机实例UUID列表；
    previous_cpu_mhz：上一次检测所有虚拟机实例额CPU利用率数据（字典）；
    added_vm_data：从中央数据库获取新添加虚拟机实例的以前的数据采集信息，用字典表示；
    """
    (cpu_time, cpu_mhz) = _get_cpu_mhz(vir_connection,
                                     init_data['physical_core_mhz'],
                                     init_data['previous_cpu_time'],
                                     init_data['previous_time'],
                                     current_time,
                                     vms_current.keys(),
                                     init_data['previous_cpu_mhz'],
                                     added_vm_data)
    
    """
    12.获取本地主机的平均CPU利用率数据（MHz）；
    注：这里是一个重点，需要好好分析；
    返回cpu_time_total（主机当前CPU总的时间），cpu_time_busy（主机当前CPU忙碌时间）
    cpu_usage（主机CPU平均利用率数据）
    """
    (host_cpu_time_total,
     host_cpu_time_busy,
     host_cpu_mhz) = _get_host_cpu_mhz(init_data['physical_cpu_mhz'],
                                     init_data['previous_host_cpu_time_total'],
                                     init_data['previous_host_cpu_time_busy'])
    
    """
    13.存储采集数据到本地存储文件中，并提交到中央数据库；
       如果是第一次采集数据，则不写入本地存储文件，也不提交到中央数据库；
      （1）存储每个虚拟机实例的CPU数据到对应的本地文件之中；
      （2）提交每个虚拟机实例的CPU数据到中央数据库之中；
      （3）计算所有虚拟机总的CPU利用率数据；
      （4）计算主机hypervisor的CPU利用率数据；
      （5）计算主机总的CPU利用率数据；
      （6）保存本地主机hpyervisor的CPU数据到指定的文件之中；
        @@@@注：这里保存的是主机平均CPU利用率减去总的虚拟机实例的CPU利用率数据的结果；
                后面分析一下欠载过载的判断标准和过程，看看这里是否有可以改进的地方，即
                其他数据是否有用武之地；
      （7）提交本地主机hpyervisor的CPU数据到中央数据库之中；
      （8）简单判断本地主机此时是否是过载的；
    """
    if init_data['previous_time'] > 0:
        _append_vm_data_locally(vm_path, cpu_mhz, data_length)
        _append_vm_data_remotely(cpu_mhz)
        total_vms_cpu_mhz = sum(cpu_mhz.values())
        host_cpu_mhz_hypervisor = host_cpu_mhz - total_vms_cpu_mhz
        if host_cpu_mhz_hypervisor < 0:
            host_cpu_mhz_hypervisor = 0
        total_cpu_mhz = total_vms_cpu_mhz + host_cpu_mhz_hypervisor
        _append_host_data_locally(host_path, host_cpu_mhz_hypervisor, data_length)
        
        _append_host_data_remotely(init_data['hostname'],
                                  host_cpu_mhz_hypervisor)
        
        """
        记录此时本地主机是否过载；
        注：此后在合适的步骤，运行状态应该更新到相关的数据表中；
        """
        init_data['previous_overload'] = _log_host_overload(
            init_data['host_cpu_overload_threshold'],
            init_data['hostname'],
            init_data['previous_overload'],
            init_data['physical_cpu_mhz'],
            total_cpu_mhz)
        
    """
    14.更新若干初始化状态数据：
    @@@@注：这里可以考虑将这些初始化的状态数据存储到数据库中
            每次进行数据采集都从数据库中读取；
    """
    init_data['previous_time'] = current_time
    init_data['previous_cpu_time'] = cpu_time
    init_data['previous_cpu_mhz'] = cpu_mhz
    init_data['previous_host_cpu_time_total'] = host_cpu_time_total
    init_data['previous_host_cpu_time_busy'] = host_cpu_time_busy
    
    try:
        host_init_data = hosts_api.update_host_init_data(init_data, host_id)
    except exception.HostInitDataNotFound:
        msg = _('host init data not found')
        raise webob.exc.HTTPBadRequest(explanation=msg)
    
    """
    15.完成一次本地虚拟机实例和主机的数据采集操作；
    """
    return True

  
def get_host_characteristics(vir_connection):
    """ 
    获取本地主机总的CPU MHZ和RAM数据；
    """
    data = vir_connection.getInfo()
    return data[2] * data[3], data[1]

def physical_cpu_count(vir_connection):
    """ 
    通过libvirt获取物理CPU的数目；
    """
    data = vir_connection.getInfo()[2]
    
    return data[2]




def _build_local_vm_path(local_data_directory):
    """ 
    建立存储本地虚拟机数据的路径；
    """
    return os.path.join(local_data_directory, 'vms')

def _build_local_host_path(local_data_directory):
    """ 
    建立存储本地本地主机数据的路径；
    """
    return os.path.join(local_data_directory, 'host')

def _get_previous_vms(path):
    """ 
    获取指定路径下的虚拟机UUID列表；
    """
    return os.listdir(path)
def _get_current_vms(vir_connection):
    """ 
    通过libvirt获取VM的UUID数据统计信息；
    """
    vm_uuids = {}
    for vm_id in vir_connection.listDomainsID():
        try:
            vm = vir_connection.lookupByID(vm_id)
            vm_uuids[vm.UUIDString()] = vm.state(0)[0]
        except libvirt.libvirtError:
            pass
    return vm_uuids

def _get_added_vms(previous_vms, current_vms):
    """ 
    通过比较新旧列表来确定新添加的虚拟机实例列表；
    """
    return _substract_lists(current_vms, previous_vms)

def _substract_lists(list1, list2):
    """ 
    Return the elements of list1 that are not in list2.
    """
    return list(set(list1).difference(list2))

def _create_new_vms_files(uuids, path):
    for uuid in uuids:
        os.mknod(os.path.join(path, uuid))
    

def _fetch_remote_data(data_length, uuids):
    """ 
    访问中央数据库获取指定uuid的虚拟机数据；
    """
    hosts_api = hosts.API()
    vm_cpu_data = dict()
    
    for uuid in uuids:
        try:
            vm_data = hosts_api.get_vm_cpu_data_by_vm_id(uuid)
        except exception.VmCpuDataNotFound:
            msg = _('vm cpu data not found')
            raise webob.exc.HTTPBadRequest(explanation=msg)
        
        vm_cpu_data_all = vm_data['cpu_data']
        data_length = vm_cpu_data_all.length
        vm_cpu_data_part = vm_cpu_data_all[data_length-10:data_length]
        vm_cpu_data[uuid] = vm_cpu_data_part
    
    return vm_cpu_data

def _write_vm_data_locally(path, data, data_length):
    """ 
    保存从中央数据库获取的新添加虚拟机实例的数据到本地存储文件；
    """
    for uuid, values in data.items():
        with open(os.path.join(path, uuid), 'w') as f:
            if data_length > 0:
                f.write('\n'.join([str(x)
                                   for x in values[-data_length:]]) + '\n')

def _get_removed_vms(previous_vms, current_vms):
    """ 
    通过比较新旧列表来确定最新删除的虚拟机实例的列表；
    """
    return _substract_lists(previous_vms, current_vms)

def _cleanup_local_vm_data(path, vms):
    """ 
    清除对应于已经删除的虚拟机实例的保存在本地的数据信息；
    """
    for vm in vms:
        os.remove(os.path.join(path, vm))
        
def _get_cpu_mhz(vir_connection, physical_core_mhz, previous_cpu_time,
                previous_time, current_time, current_vms,
                previous_cpu_mhz, added_vm_data):
    """ 
    获取虚拟机实例的平均CPU利用率数据（MHz）；
    返回所有虚拟机实例vm的previous_cpu_time和所有虚拟机实例vm的cpu利用率；
    @@@@注：好好分析这个方法；
    
    vir_connection：到libvirt的连接；
    physical_core_mhz：每个物理CPU core的频率（MHz）；
    本地主机总的CPU MHZ频率除以物理CPU的个数；
    previous_cpu_time：上一次的虚拟机的CPU时间（字典）；
    previous_time：上一次的时间戳；
    current_time：当前的时间戳；
    current_vms：当前的虚拟机实例UUID列表；
    previous_cpu_mhz：上一次检测所有虚拟机实例额CPU利用率数据（字典）；
    added_vm_data：从中央数据库获取新添加虚拟机实例的以前的数据采集信息，用字典表示；

    :return: The updated CPU times and average CPU utilization in MHz.
     :rtype: tuple(dict(str : int), dict(str : int))
     返回更新的CPU时间和平均的CPU利用率（MHz）信息；
    """
    """
    确定在上一次数据采集中，虚拟机实例的列表；
    """
    previous_vms = previous_cpu_time.keys()
    """
    通过比较获取新添加（新迁移过来的）虚拟机实例的列表；
    """
    added_vms = _get_added_vms(previous_vms, current_vms)
    """
    通过比较获取最新删除的虚拟机实例的列表；
    """
    removed_vms = _get_removed_vms(previous_vms, current_vms)
    cpu_mhz = {}

    """
    对于最新删除的虚拟机实例列表，删除其相关的previous_cpu_time数据信息；
    """
    for uuid in removed_vms:
        del previous_cpu_time[uuid]

    """
    针对原有虚拟机实例（去除了最新删除的虚拟机实例）的cpu利用率计算：
    cpu利用率 = 
    物理CPU core的频率X(当前虚拟机实例的CPU时间-上一次虚拟机实例的CPU时间)/
    (当前的时间戳-上一次时间戳)X1000000000
    """
    for uuid, cpu_time in previous_cpu_time.items():
        """
        通过libvirt获取指定UUID的虚拟机实例的CPU时间；
        """
        current_cpu_time = _get_cpu_time(vir_connection, uuid)
        if current_cpu_time < cpu_time:
            cpu_mhz[uuid] = previous_cpu_mhz[uuid]
        else:
            """
            计算指定UUID的虚拟机实例某一段时间内的CPU平均利用率数据；
            physical_core_mhz：物理CPU core的频率（MHz）；
            previous_time：上一次的时间戳；
            current_time：当前的时间戳；
            cpu_time：上一次的虚拟机的CPU时间；
            current_cpu_time：当前虚拟机实例的CPU时间；
            """
            cpu_mhz[uuid] = _calculate_cpu_mhz(physical_core_mhz, previous_time,
                                              current_time, cpu_time,
                                              current_cpu_time)
        """
        更新指定uuid虚拟机实例的previous_cpu_time值；
        """
        previous_cpu_time[uuid] = current_cpu_time

    """
    针对新添加或新迁移过来的虚拟机实例的cpu利用率计算：
    对于新添加的或者新迁移过来的虚拟机实例，
    因为相关数据的缺失，无法直接计算当前的cpu利用率数据，
    所以直接从中央数据库获取其之前的cpu利用率数据，
    将其最近一次cpu利用率数据作为当前的cpu利用率数据；
    
    直接从中央数据库获取新添加虚拟机实例以前的数据采集信息，
    用字典表示，即added_vm_data；
    """
    for uuid in added_vms:
        if added_vm_data[uuid]:
            cpu_mhz[uuid] = added_vm_data[uuid][-1]
        previous_cpu_time[uuid] = _get_cpu_time(vir_connection, uuid)

    """
    返回所有虚拟机实例vm的previous_cpu_time和所有虚拟机实例vm的cpu利用率；
    """
    return previous_cpu_time, cpu_mhz

def _get_cpu_time(vir_connection, uuid):
    """ 
    Get the CPU time of a VM specified by the UUID using libvirt.
    通过libvirt获取指定UUID的虚拟机实例的CPU时间；

    :param vir_connection: A libvirt connection object.
     :type vir_connection: virConnect

    :param uuid: The UUID of a VM.
     :type uuid: str[36]

    :return: The CPU time of the VM.
     :rtype: int,>=0
    """
    try:
        domain = vir_connection.lookupByUUIDString(uuid)
        return int(domain.getCPUStats(True, 0)[0]['cpu_time'])
    except libvirt.libvirtError:
        return 0

def _calculate_cpu_mhz(cpu_mhz, previous_time, current_time,
                      previous_cpu_time, current_cpu_time):
    """ 
    Calculate the average CPU utilization in MHz for a period of time.
    计算某一段时间内的CPU平均利用率数据；

    
    :param cpu_mhz: The frequency of a core of the physical CPU in MHz.
     :type cpu_mhz: int
     physical_core_mhz：物理CPU core的频率（MHz）；

    :param previous_time: The previous time.
     :type previous_time: float
     previous_time：上一次的时间戳；

    :param current_time: The current time.
     :type current_time: float
     current_time：当前的时间戳；

    :param previous_cpu_time: The previous CPU time of the domain.
     :type previous_cpu_time: int
     cpu_time：上一次的虚拟机的CPU时间；

    :param current_cpu_time: The current CPU time of the domain.
     :type current_cpu_time: int
     current_cpu_time：当前虚拟机实例的CPU时间；

    :return: The average CPU utilization in MHz.
     :rtype: int,>=0
    """
    return int(cpu_mhz * float(current_cpu_time - previous_cpu_time) / \
               ((current_time - previous_time) * 1000000000))
    
def _get_host_cpu_mhz(cpu_mhz, previous_cpu_time_total, previous_cpu_time_busy):
    """ 
    Get the average CPU utilization in MHz for a set of VMs.
    为虚拟机实例集合（主机）获取平均CPU利用率数据；
    返回cpu_time_total（主机当前CPU总的时间），cpu_time_busy（主机当前CPU忙碌时间）
    cpu_usage（主机CPU平均利用率数据）

    :param cpu_mhz: The total frequency of the physical CPU in MHz.
     :type cpu_mhz: int
     state['physical_cpu_mhz']：host_cpu_mhz（host_cpu_mhz和host_ram都是通过libvirt获取）
     物理CPU总的频率数据；
     
    :param previous_cpu_time_total: The previous total CPU time.
     :type previous_cpu_time_total: float
     state['previous_host_cpu_time_total']：0.
     上一次主机总的CPU时间；

    :param previous_cpu_time_busy: The previous busy CPU time.
     :type previous_cpu_time_busy: float
     state['previous_host_cpu_time_busy']：0.
     上一次主机CPU忙碌时间；

    :return: The current total and busy CPU time, and CPU utilization in MHz.
     :rtype: tuple(float, float, int)
     返回cpu_time_total（主机当前CPU总的时间），cpu_time_busy（主机当前CPU忙碌时间）
     cpu_usage（主机CPU平均利用率数据）
    """
    
    """
    获取主机总的CPU时间和CPU忙碌时间（直接通过读取/proc/stat文件获取）；
    """
    cpu_time_total, cpu_time_busy = _get_host_cpu_time()
    """
    计算主机CPU平均利用率数据；
    """
    cpu_usage = int(cpu_mhz * (cpu_time_busy - previous_cpu_time_busy) / \
                    (cpu_time_total - previous_cpu_time_total))
    if cpu_usage < 0:
        raise ValueError('The host CPU usage in MHz must be >=0, but it is: ' + str(cpu_usage) +
                         '; cpu_mhz=' + str(cpu_mhz) +
                         '; previous_cpu_time_total=' + str(previous_cpu_time_total) +
                         '; cpu_time_total=' + str(cpu_time_total) +
                         '; previous_cpu_time_busy=' + str(previous_cpu_time_busy) +
                         '; cpu_time_busy=' + str(cpu_time_busy))
    return cpu_time_total, \
           cpu_time_busy, \
           cpu_usage

def _get_host_cpu_time():
    """ 
    Get the total and busy CPU time of the host.
    获取主机总的CPU时间和CPU忙碌时间（直接通过读取/proc/stat文件获取）；

    :return: A tuple of the total and busy CPU time.
     :rtype: tuple(float, float)
    """
    with open('/proc/stat', 'r') as f:
        values = [float(x) for x in f.readline().split()[1:8]]
        return sum(values), sum(values[0:3])
    
def _append_vm_data_locally(path, data, data_length):
    """ 
    Write a CPU MHz value for each out of a set of VMs.
    存储每个虚拟机实例的CPU数据到对应的本地文件中；

    :param path: A path to write the data to.
     :type path: str

    :param data: A map of VM UUIDs onto the corresponing CPU MHz values.
     :type data: dict(str : int)

    :param data_length: The maximum allowed length of the data.
     :type data_length: int
    """
    for uuid, value in data.items():
        vm_path = os.path.join(path, uuid)
        if not os.access(vm_path, os.F_OK):
            with open(vm_path, 'w') as f:
                f.write(str(value) + '\n')
        else:
            with open(vm_path, 'r+') as f:
                values = deque(f.read().strip().splitlines(), data_length)
                values.append(value)
                f.truncate(0)
                f.seek(0)
                f.write('\n'.join([str(x) for x in values]) + '\n')
                
def _append_vm_data_remotely(db, data):
    """ 
    Submit CPU MHz values to the central database.
    提交CPU数据到中央数据库中；
    @@@@注：这里查看nova中数据库操作的具体实现方式；

    :param db: The database object.
     :type db: Database

    :param data: A map of VM UUIDs onto the corresponing CPU MHz values.
     :type data: dict(str : int)
    """
    db.insert_vm_cpu_mhz(data)

def _append_host_data_locally(path, cpu_mhz, data_length):
    """ 
    保存本地主机的CPU数据到指定的文件中；

    :param path: A path to write the data to.
     :type path: str

    :param cpu_mhz: A CPU MHz value.
     :type cpu_mhz: int,>=0

    :param data_length: The maximum allowed length of the data.
     :type data_length: int
    """
    if not os.access(path, os.F_OK):
        with open(path, 'w') as f:
            f.write(str(cpu_mhz) + '\n')
    else:
        with open(path, 'r+') as f:
            values = deque(f.read().strip().splitlines(), data_length)
            values.append(cpu_mhz)
            f.truncate(0)
            f.seek(0)
            f.write('\n'.join([str(x) for x in values]) + '\n')
            
def _append_host_data_remotely(db, hostname, host_cpu_mhz):
    """ 
    提交本地主机的CPU数据到中心数据库中；

    :param db: The database object.
     :type db: Database

    :param hostname: The host name.
     :type hostname: str

    :param host_cpu_mhz: An average host CPU utilization in MHz.
     :type host_cpu_mhz: int,>=0
    """
    db.insert_host_cpu_mhz(hostname, host_cpu_mhz)
    
def _log_host_overload(overload_threshold, hostname, previous_overload,
                      host_total_mhz, host_utilization_mhz):
    """ 
    Log to the DB whether the host is overloaded.
    """
    overload = overload_threshold * host_total_mhz < host_utilization_mhz
    overload_int = int(overload)

    return overload_int