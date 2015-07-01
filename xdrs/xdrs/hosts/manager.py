import os
import webob
from webob import exc
import subprocess
from oslo.config import cfg
import libvirt

from xdrs import manager
from xdrs.hosts import rpcapi as hosts_rpcapi
from xdrs import conductor
from xdrs import hosts
from xdrs import exception
from xdrs import states
import xdrs
from xdrs.hosts import data_collection
from xdrs.hosts import load_detection
from xdrs.hosts import vms_selection

from __future__ import print_function
from collections import OrderedDict

CONF = cfg.CONF
CONF.import_opt('local_data_directory', 'xdrs.service')

class HostManager(manager.Manager):
    def __init__(self, compute_driver=None, *args, **kwargs):
        """Load configuration options and connect to the hypervisor."""
        self._last_host_check = 0
        self._last_bw_usage_poll = 0
        self._bw_usage_supported = True
        self._last_bw_usage_cell_update = 0
        
        self.hosts_rpcapi = hosts_rpcapi.HostRPCAPI()
        self.conductor_api = conductor.API()
        self._resource_tracker_dict = {}

        super(HostManager, self).__init__(service_name="xdrs_host",
                                             *args, **kwargs)
    
    """
    **************
    * algorithms *
    **************
    """
    def get_all_algorithms_sorted_list(self, context): 
        return self.conductor_api.get_all_algorithms_sorted_list(context)
    
    def get_all_overload_algorithms_sorted_list(self, context):
        return self.conductor_api.get_all_overload_algorithms_sorted_list(context)

    def get_all_underload_algorithms_sorted_list(self, context):
        return self.conductor_api.get_all_underload_algorithms_sorted_list(context)
    
    def get_all_filter_scheduler_algorithms_sorted_list(self, context):
        return self.conductor_api.get_all_filter_scheduler_algorithms_sorted_list(context)
    
    def get_all_host_scheduler_algorithms_sorted_list(self, context): 
        return self.conductor_api.get_all_host_scheduler_algorithms_sorted_list(context)
    
    def get_all_vm_select_algorithm_sorted_list(self, context):
        return self.conductor_api.get_all_vm_select_algorithm_sorted_list(context)
    
    def get_overload_algorithm_by_id(self, context, id):
        return self.conductor_api.get_overload_algorithm_by_id(context, id)
    
    def get_underload_algorithm_by_id(self, context, id):
        return self.conductor_api.get_underload_algorithm_by_id(context, id)
    
    def get_filter_scheduler_algorithm_by_id(self, context, id):
        return self.conductor_api.get_filter_scheduler_algorithm_by_id(context, id)
    
    def get_host_scheduler_algorithm_by_id(self, context, id):
        return self.conductor_api.get_host_scheduler_algorithm_by_id(context, id)
    
    def get_vm_select_algorithm_by_id(self, context, id):
        return self.conductor_api.get_vm_select_algorithm_by_id(context, id)
    
    def delete_overload_algorithm_by_id(self, context, id):
        return self.conductor_api.delete_overload_algorithm_by_id(context, id)
    
    def delete_underload_algorithm_by_id(self, context, id):
        return self.conductor_api.delete_underload_algorithm_by_id(context, id)
    
    def delete_filter_scheduler_algorithm_by_id(self, context, id):
        return self.conductor_api.delete_filter_scheduler_algorithm_by_id(context, id)
    
    def delete_host_scheduler_algorithm_by_id(self, context, id):
        return self.conductor_api.delete_host_scheduler_algorithm_by_id(context, id)
    
    def delete_vm_select_algorithm_by_id(self, context, id):
        return self.conductor_api.delete_vm_select_algorithm_by_id(context, id)
    
    """
    注：这里应该改变配置文件中的参数信息，而不应该是改变数据库中的参数信息；
    """
    def update_overload_algorithm(self, context, id, values):
        return self.conductor_api.update_overload_algorithm(context, id, values)
    
    """
    注：这里应该改变配置文件中的参数信息，而不应该是改变数据库中的参数信息；
    """
    def update_underload_algorithm(self, context, id, values):
        return self.conductor_api.update_underload_algorithm(context, id, values)
    
    """
    注：这里应该改变配置文件中的参数信息，而不应该是改变数据库中的参数信息；
    """
    def update_filter_scheduler_algorithm(self, context, id, values):
        return self.conductor_api.update_filter_scheduler_algorithm(context, id, values)
    
    """
    注：这里应该改变配置文件中的参数信息，而不应该是改变数据库中的参数信息；
    """
    def update_host_scheduler_algorithm(self, context, id, values):
        return self.conductor_api.update_host_scheduler_algorithm(context, id, values)
    
    """
    注：这里应该改变配置文件中的参数信息，而不应该是改变数据库中的参数信息；
    """
    def update_vm_select_algorithm(self, context, id, values):
        return self.conductor_api.update_vm_select_algorithm(context, id, values)
    
    def create_underload_algorithm(self, context, algorithm_create_values):
        return self.conductor_api.create_underload_algorithm(context, algorithm_create_values)
    
    def create_overload_algorithm(self, context, algorithm_create_values):
        return self.conductor_api.create_overload_algorithm(context, algorithm_create_values)
    
    def create_filter_scheduler_algorithm(self, context, algorithm_create_values):
        return self.conductor_api.create_filter_scheduler_algorithm(context, algorithm_create_values)
    
    def create_host_scheduler_algorithm(self, context, algorithm_create_values):
        return self.conductor_api.create_host_scheduler_algorithm(context, algorithm_create_values)
    
    def create_vm_select_algorithm(self, context, algorithm_create_values):
        return self.conductor_api.create_vm_select_algorithm(context, algorithm_create_values)
    
    def get_overload_algorithm_in_used(self, context):
        return self.conductor_api.get_overload_algorithm_in_used(context)

    def get_underload_algorithm_in_used(self, context):
        return self.conductor_api.get_underload_algorithm_in_used(context)

    def get_filter_scheduler_algorithms_in_used(self, context):
        return self.conductor_api.get_filter_scheduler_algorithms_in_used(context)

    def get_host_scheduler_algorithm_in_used(self, context):
        return self.conductor_api.get_host_scheduler_algorithm_in_used(context)
    
    def get_vm_select_algorithm_in_used(self, context):
        return self.conductor_api.get_vm_select_algorithm_in_used(context)
    
    """
    *****************
    * host_cpu_data *
    *****************
    """
    def get_all_host_cpu_data(self, context):
        return self.conductor_api.get_all_host_cpu_data(context)
    
    def get_host_cpu_data_by_id(self, context, id):
        return self.conductor_api.get_host_cpu_data_by_id(context, id)
    
    def create_host_cpu_data_temp_by_id(self, context, update_values, host_uuid):
        return self.conductor_api.create_host_cpu_data_temp_by_id(context, update_values, host_uuid)
    
    def update_host_cpu_data_temp_by_id(self, context, update_values, host_uuid):
        return self.conductor_api.update_host_cpu_data_temp_by_id(context, update_values, host_uuid)
    
    def get_host_cpu_data_temp_by_id(self, context, host_uuid):
        return self.conductor_api.get_host_cpu_data_temp_by_id(context, host_uuid)
    
    
    
    """
    *****************
    * hosts_states *
    *****************
    """
    def get_all_hosts_states(self, context):
        return self.conductor_api.get_all_hosts_states(context)
    
    def get_host_task_states_by_id(self, context, id):
        return self.conductor_api.get_host_task_states_by_id(context, id)
            
    def delete_host_task_states_by_id(self, context, id):
        return self.conductor_api.delete_host_task_states_by_id(context, id)
            
    def update_host_task_states(self, context, id, update_value):
        return self.conductor_api.update_host_task_states(context, id, update_value)
            
    def get_all_hosts_task_states_sorted_list(self, context):
        return self.conductor_api.get_all_hosts_task_states_sorted_list(context)     
    
    def get_host_running_states_by_id(self, context, id):
        return self.conductor_api.get_host_running_states_by_id(context, id)
            
    def update_host_running_states(self, context, id, update_value):
        return self.conductor_api.update_host_running_states(context, id, update_value)
            
    def delete_host_running_states_by_id(self, context, id):
        return self.conductor_api.delete_host_running_states_by_id(context, id)
            
    def get_all_hosts_running_states_sorted_list(self, context):
        return self.conductor_api.get_all_hosts_running_states_sorted_list(context)   
    
    def get_host_load_states_by_id(self, context, id):
        return self.conductor_api.get_host_load_states_by_id(context, id)
            
    def update_host_load_states(self, context, id, update_value):
        return self.conductor_api.update_host_load_states(context, id, update_value)
            
    def delete_host_load_states_by_id(self, context, id):
        return self.conductor_api.delete_host_load_states_by_id(context, id)
            
    def get_all_hosts_load_states_sorted_list(self, context):
        return self.conductor_api.get_all_hosts_load_states_sorted_list(context)
    
    
    
    """
    ******************
    * host_init_data *
    ******************
    """
    def create_host_init_data(self, context, update_values):
        return self.conductor_api.create_host_init_data(context, update_values)
    
    def update_host_init_data(self, context, host_id, update_values):
        return self.conductor_api.update_host_init_data(context, host_id, update_values)
    
    def get_host_init_data(self, context, host_id):
        return self.conductor_api.get_host_init_data(context, host_id)
    
    def get_all_hosts_init_data(self, context):
        return self.conductor_api.get_all_hosts_init_data(context)
    
    def create_host_init_data_temp(self, context, update_values):
        return self.conductor_api.create_host_init_data_temp(context, update_values)
    
    def update_host_init_data_temp(self, context, host_id, update_values):
        return self.conductor_api.update_host_init_data_temp(context, host_id, update_values)
    
    def get_host_init_data_temp(self, context, host_uuid_temp):
        return self.conductor_api.get_host_init_data_temp(context, host_uuid_temp)
    
    """
    ***************
    * vm_cpu_data *
    ***************
    """
    def get_all_vms_cpu_data(self, context):
        return self.conductor_api.get_all_vms_cpu_data(context)
            
    def get_vm_cpu_data_by_vm_id(self, context, vm_id):
        return self.conductor_api.get_vm_cpu_data_by_vm_id(context, vm_id)
            
    def delete_vm_cpu_data_by_vm_id(self, context, vm_id):
        vm_path = CONF.local_data_directory + '/' + vm_id
        
        if os.path.exists(vm_path):
            if os.path.isfile(vm_path):
                os.remove(vm_path)
        
        result = self.conductor_api.delete_vm_cpu_data_by_vm_id(context, vm_id)
        return result
    
    def get_vm_cpu_data_by_host_id(self, context, host_id):
        return self.conductor_api.get_vm_cpu_data_by_host_id(context, host_id)
    
    def delete_vm_cpu_data_by_host_id(self, context, host_id):
        return self.conductor_api.delete_vm_cpu_data_by_host_id(context, host_id)
    

    
    """
    ****************
    * host_meminfo *
    ****************
    """
    def get_meminfo_by_id(self, context):
        ''' 
        Return the information in /proc/meminfo
        as a dictionary 
        '''
        meminfo=OrderedDict()
        
        with open('/proc/meminfo') as f:
            for line in f:
                meminfo[line.split(':')[0]] = line.split(':')[1].strip()
        
        return meminfo
    
    
    """
    *******************
    * vms on host ram *
    *******************
    """
    def get_vms_ram_on_specific(self, context, vms_list):
        """ 
        为每一个UUID指定的虚拟机实例的获取其最大RAM值；
        """
        vir_connection = libvirt.openReadOnly(None)
        
        vms_ram = {}
        for uuid in vms_list:
            """
            通过libvirt获取分配给指定UUID的虚拟机实例的最大RAM值；
            """
            ram = self._get_max_ram(vir_connection, uuid)
            if ram:
                vms_ram[uuid] = ram
                
        return vms_ram
    
    def _get_max_ram(self, vir_connection, uuid):
        """ 
        通过libvirt获取分配给指定UUID的虚拟机实例的最大RAM值；
        """
        try:
            domain = vir_connection.lookupByUUIDString(uuid)
            return domain.maxMemory() / 1024
        except libvirt.libvirtError:
            return None
        
    
    
    """
    **************
    * host_power *
    **************
    """
    def switch_host_off(self, context, sleep_command, host):
        """ 
        切换主机到低功耗模式；
        更新本地主机的功耗运行模式；
        """
        if sleep_command:
            command = 'ssh {0} "{1}"'. format(host, sleep_command)
            subprocess.call(command, shell=True)
            
        try:
            host_running_states = self.hosts_api.update_host_running_states(context, host, states.LOW_POWER)
        except exception.HostRunningStateNotFound as ex:
            raise webob.exc.HTTPNotFound(explanation=ex.format_message())
        
        return states.LOW_POWER
    
    def switch_host_on(self, context, ether_wake_interface, host_macs, host):
        """ 
        切换主机到活跃模式；
        """
        """
        如果没有指定mac地址，则获取指定主机的mac地址；
        注：mac概念弄清楚，还有就是有多网卡的情况下，如何确定唤醒哪个网卡；
        """
        if host not in host_macs:
            host_macs[host] = self._host_mac(host)
        """
        读取配置文件ether_wake_interface = eth0；
        """
        command = 'ether-wake -i {0} {1}'.format(
            ether_wake_interface,
            host_macs[host])
        subprocess.call(command, shell=True)
        
        """
        记录主机状态到数据库；
        """
        try:
            host_running_states = self.hosts_api.update_host_running_states(context, host, states.NORMAL_POWER)
        except exception.HostRunningStateNotFound as ex:
            raise webob.exc.HTTPNotFound(explanation=ex.format_message())
        
        return states.NORMAL_POWER
    
    
    def _host_mac(self, host):
        """ 
        Get mac address of a host.
        获取指定主机的mac地址；

        :param host: A host name.
        :type host: str

        :return: The mac address of the host.
        :rtype: str
        """
        mac = subprocess.Popen(
            ("ping -c 1 {0} > /dev/null;" +
             "arp -a {0} | awk '{{print $4}}'").format(host),
            stdout=subprocess.PIPE,
            shell=True).communicate()[0].strip()
        return mac
    
    
    def compute_host_cpu_mhz(self, context, host_uuid_temp):
        hosts_api = hosts.API()
        
        try:
            host_init_data_temp = hosts_api.get_host_init_data_temp(context, host_uuid_temp)
        except exception.HostInitDataNotFound:
            msg = _('host init data not found')
            raise webob.exc.HTTPBadRequest(explanation=msg)
        
        physical_cpu_mhz = host_init_data_temp['physical_cpu_mhz']
        previous_host_cpu_time_total = host_init_data_temp['previous_host_cpu_time_total']
        previous_host_cpu_time_busy = host_init_data_temp['previous_host_cpu_time_busy']
        
        (host_cpu_time_total,
         host_cpu_time_busy,
         host_cpu_mhz) = self._get_host_cpu_mhz(physical_cpu_mhz,
                                          previous_host_cpu_time_total,
                                          previous_host_cpu_time_busy)
         
         
         
    def _get_host_cpu_mhz(self, cpu_mhz, previous_cpu_time_total, previous_cpu_time_busy):
        """ 
        为虚拟机实例集合（主机）获取平均CPU利用率数据；
        返回cpu_time_total（主机当前CPU总的时间），cpu_time_busy（主机当前CPU忙碌时间）
        cpu_usage（主机CPU平均利用率数据）
        
        state['physical_cpu_mhz']：host_cpu_mhz（host_cpu_mhz和host_ram都是通过libvirt获取）
        物理CPU总的频率数据；
        
        previous_cpu_time_total: The previous total CPU time.
        上一次主机总的CPU时间；
        
        previous_cpu_time_busy: The previous busy CPU time.
        上一次主机CPU忙碌时间；
        
        返回cpu_time_total（主机当前CPU总的时间），cpu_time_busy（主机当前CPU忙碌时间）
        cpu_usage（主机CPU平均利用率数据）
        """
        
        """
        获取主机总的CPU时间和CPU忙碌时间（直接通过读取/proc/stat文件获取）；
        """
        cpu_time_total, cpu_time_busy = self._get_host_cpu_time()
        """
        计算主机CPU平均利用率数据；
        """
        cpu_usage = int(cpu_mhz * (cpu_time_busy - previous_cpu_time_busy) / \
                    (cpu_time_total - previous_cpu_time_total))
        
        return cpu_time_total, cpu_time_busy, cpu_usage
    
    def _get_host_cpu_time(self):
        """ 
        获取主机总的CPU时间和CPU忙碌时间（直接通过读取/proc/stat文件获取）；
        """
        with open('/proc/stat', 'r') as f:
            values = [float(x) for x in f.readline().split()[1:8]]
            return sum(values), sum(values[0:3])
        
    def init_host(self):
        context = xdrs.context.get_admin_context()
        
        """
        获取本地主机名local_host;
        """
        local_host = ''
        
        try:
            host_task_states = self.hosts_api.get_host_task_states_by_id(context, local_host)
        except exception.NotFound:
            raise exc.HTTPNotFound()
        
        if host_task_states is None:
            update_value = {'host_task_state': 'do_nothing'} 
            try:
                host_task_states = self.hosts_api.update_host_task_states(context, local_host, update_value)
            except exception.HostTaskStateNotFound as ex:
                raise webob.exc.HTTPNotFound(explanation=ex.format_message())
        
        try:
            host_running_states = self.hosts_api.get_host_running_states_by_id(context, local_host)
        except exception.NotFound:
            raise exc.HTTPNotFound()
        
        if host_running_states is None:
            update_value = {'host_running_states': 'normal_power'} 
            try:
                host_running_states = self.hosts_api.update_host_running_states(context, local_host, update_value)
            except exception.HostRunningStateNotFound as ex:
                raise webob.exc.HTTPNotFound(explanation=ex.format_message())
        
        try:
            host_load_states = self.hosts_api.get_host_load_states_by_id(context, local_host)
        except exception.NotFound:
            raise exc.HTTPNotFound()
        
        if host_load_states is None:
            update_value = {'host_load_states': 'normalload'} 
            try:
                host_load_states = self.hosts_api.update_host_load_states(context, local_host, update_value)
            except exception.HostLoadStateNotFound as ex:
                raise webob.exc.HTTPNotFound(explanation=ex.format_message())
    
    

class DataCollectionManager(manager.Manager):
    def __init__(self, compute_driver=None, *args, **kwargs):
        """Load configuration options and connect to the hypervisor."""
        self._last_host_check = 0
        self._last_bw_usage_poll = 0
        self._bw_usage_supported = True
        self._resource_tracker_dict = {}

        super(DataCollectionManager, self).__init__(service_name="xdrs_data_collection",
                                             *args, **kwargs)
        
    
    def hosts_vms_data_collection(self, context):
        try:
            hosts_vms_data_collection = data_collection.local_data_collector(context)
        except exception.DataCollectionError:
            msg = _('There are some error in hosts and vms data collection operation.')
            raise webob.exc.HTTPBadRequest(explanation=msg)
        
        return hosts_vms_data_collection
    


class LoadDetectionManager(manager.Manager):
    def __init__(self, compute_driver=None, *args, **kwargs):
        """Load configuration options and connect to the hypervisor."""
        self._last_host_check = 0
        self._last_bw_usage_poll = 0
        self._bw_usage_supported = True
        self._resource_tracker_dict = {}

        super(LoadDetectionManager, self).__init__(service_name="xdrs_load_detection",
                                             *args, **kwargs)
    
    
    def hosts_load_detection(self, context):
        try:
            hosts_load_detection = load_detection.local_load_detect(context)
        except exception.LoadDetectionError:
            msg = _('There are some error in hosts load detection operation.')
            raise webob.exc.HTTPBadRequest(explanation=msg)
        
        return hosts_load_detection
    

    
    
class VmsSelectionManager(manager.Manager):
    def __init__(self, compute_driver=None, *args, **kwargs):
        """Load configuration options and connect to the hypervisor."""
        self._last_host_check = 0
        self._last_bw_usage_poll = 0
        self._bw_usage_supported = True
        self._resource_tracker_dict = {}

        super(VmsSelectionManager, self).__init__(service_name="xdrs_vms_seletcion",
                                             *args, **kwargs)
        
    
    def vms_selection(self, context):
        try:
            vms_migration_selection = vms_selection.local_vms_select(context)
        except exception.VmsSelectionError:
            msg = _('There are some error in vms selection operation.')
            raise webob.exc.HTTPBadRequest(explanation=msg)
        
        return vms_migration_selection
    


class VmsMigrationManager(manager.Manager):
    def __init__(self, compute_driver=None, *args, **kwargs):
        """Load configuration options and connect to the hypervisor."""
        self._last_host_check = 0
        self._last_bw_usage_poll = 0
        self._bw_usage_supported = True
        self._resource_tracker_dict = {}

        super(VmsMigrationManager, self).__init__(service_name="xdrs_vms_migration",
                                             *args, **kwargs)