import webob
from webob import exc
from oslo.config import cfg
import time
import libvirt
import random

from xdrs import manager
from xdrs import hosts
from xdrs import exception
import xdrs
from xdrs.compute.nova import novaclient
from xdrs.controller import rpcapi as data_collection_rpcapi
from xdrs.controller import rpcapi as load_detection_rpcapi
from xdrs.controller import rpcapi as vms_selection_rpcapi
from xdrs.controller import rpcapi as vms_migration_rpcapi
from xdrs.controller import rpcapi as controller_rpcapi

CONF = cfg.CONF
CONF.import_opt('data_collection_topic', 'xdrs.service')
CONF.import_opt('load_detection_topic', 'xdrs.service')
CONF.import_opt('vms_migration_topic', 'xdrs.service')
CONF.import_opt('vms_selection_topic', 'xdrs.service')
CONF.import_opt('wait_time', 'xdrs.service')
CONF.import_opt('controller_topic', 'xdrs.service')
CONF.import_opt('host_scheduler_algorithm_path', 'xdrs.service')
CONF.import_opt('sleep_command', 'xdrs.service')
CONF.import_opt('filter_scheduler_algorithm_path', 'xdrs.service')

class ControllerManager(manager.Manager):
    def __init__(self, compute_driver=None, *args, **kwargs):
        self.hosts_api = hosts.API()
        self.data_collection_rpcapi = data_collection_rpcapi.DataCollectionRPCAPI()
        self.load_detection_rpcapi = load_detection_rpcapi.LoadDetectionRPCAPI()
        self.vms_selection_rpcapi = vms_selection_rpcapi.VmsSelectionRPCAPI()
        self.vms_migration_rpcapi = vms_migration_rpcapi.VmMigrationRPCAPI()
        self.controller_rpcapi = controller_rpcapi.ControllerRPCAPI()
        super(ControllerManager, self).__init__(service_name="xdrs_controller",
                                             *args, **kwargs)
        
    """
    *******************
    * vm_host_miration *
    ********************
    """
    def vm_to_host_migrate(self, context, vm, orig_host, dest_host):
        return novaclient(context).servers.live_migrate(vm, dest_host, False, False)
    
    
    
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
        try:
            host_state = self.hosts_api.switch_host_off(context, sleep_command, host)
        except exception.NotFound:
            raise exc.HTTPNotFound()
        
        return host_state
    
    def switch_host_on(self, context, ether_wake_interface, host_macs, host):
        """ 
        切换主机到活跃模式；
        """
        try:
            host_state = self.hosts_api.switch_host_on(context, 
                                                      ether_wake_interface, 
                                                      host_macs,
                                                      host)
        except exception.NotFound:
            raise exc.HTTPNotFound()
        
        return host_state
    
    
    def dynamic_resource_scheduling(self, context):
        controller_topic = CONF.controller_topic
        data_collection_topic = CONF.data_collection_topic
        load_detection_topic = CONF.load_detection_topic
        vms_selection_topic = CONF.vms_selection_topic
        vms_migration_topic = CONF.vms_migration_topic
        
        """
        所有主机uuid信息；
        """
        hosts = dict()
        hosts_uuid = dict()
        
        try:
            hosts_init_data = self.hosts_api.get_all_hosts_init_data(context)
        except exception.HostInitDataNotFound:
            msg = _('host init data not found')
            raise webob.exc.HTTPBadRequest(explanation=msg)
        
        for host_init_data in hosts_init_data:
            host_uuid = host_init_data['host_id']
            host_name = host_init_data['host_name']
            hosts_uuid.add(host_uuid)
            hosts[host_uuid] = host_name
        
        
        """
        所有主机本地数据采集；
        """
        try:
            self.data_collection_rpcapi.hosts_vms_data_collection(context, data_collection_topic)
        except exception.DataCollectionError:
            msg = _('There are some error in hosts and vms data collection operation.')
            raise webob.exc.HTTPBadRequest(explanation=msg)
        
        time.sleep(CONF.wait_time)
        
        
        """
        所有主机本地负载检测；
        """
        try:
            self.load_detection_rpcapi.hosts_load_detection(context, load_detection_topic)
        except exception.LoadDetectionError:
            msg = _('There are some error in hosts load detection operation.')
            raise webob.exc.HTTPBadRequest(explanation=msg)
        
        time.sleep(CONF.wait_time)
        
        
        """
        针对负载状态为过载的主机，选取其上合适数量的虚拟机实例，以便进行虚拟机的迁移操作；
        """
        vms_mrigation_selection = dict()
        underload_hosts_uuid = list()
        for host_uuid in hosts_uuid:
            try:
                host_load_states = self.hosts_api.get_host_load_states_by_id(context, host_uuid)
            except exception.NotFound:
                raise exc.HTTPNotFound()
            
            host_load_state = host_load_states['host_load_state']
            
            if host_load_state == 'underload':
                underload_hosts_uuid.add(host_uuid)
            
            if host_load_state == 'overload':
                try:
                    vm_mrigation_list = self.vms_selection_rpcapi.vms_selection(context, host_uuid, vms_selection_topic)
                except exception.VmsSelectionError:
                    msg = _('There are some error in vms selection operation.')
                    raise webob.exc.HTTPBadRequest(explanation=msg)
                
                vms_mrigation_selection[host_uuid] = vm_mrigation_list
           
        
        time.sleep(CONF.wait_time)
        
        """
        针对过载主机的要迁移的虚拟机实例进行迁移目标主机的分配；
        选取虚拟机----主机映射算法；
        """
        host_scheduler_algorithm = self.hosts_api.get_vm_select_algorithm_in_used(context)
        host_scheduler_algorithm_name = host_scheduler_algorithm['algorithm_name']
        host_scheduler_algorithm_fuction = CONF.host_scheduler_algorithm_path + '.' + host_scheduler_algorithm_name
        vms_hosts_mapper = dict()
        
        
        """
        针对可用的目标主机列表，复制其HostCpuData中的cpu_data数据到临时数据表HostCpuDataTemp中，
        以便在为所有需要迁移的虚拟机实例选取目标主机的算法中应用；
        因为要进行虚拟机的预迁移操作，会若干次改变不同目标主机的cpu_data，为了不改变HostCpuData中
        的数据，所以这里要对其复制生成临时的数据表HostCpuDataTemp。
        HostCPUDataTemp这里包括主机内存的使用信息，数据表名称有待商榷；
        """
        for host_uuid, vm_mrigation_list in vms_mrigation_selection:
            try:
                cpu_data = self.hosts_api.get_host_cpu_data_by_id(context, host_uuid)
            except exception.HostCpuDataNotFound:
                msg = _('host cpu data not found')
                raise webob.exc.HTTPBadRequest(explanation=msg)
            
            try:
                host_meminfo = self.hosts_api.get_meminfo_by_id(context, host_uuid)
            except exception.HostMemroyInfoNotFound:
                msg = _('host memroy info not found')
                raise webob.exc.HTTPBadRequest(explanation=msg)
            
            update_values = (cpu_data, host_meminfo)
            
            try:
                hosts_cpu_data_temp = self.hosts_api.create_host_cpu_data_temp_by_id(context, update_values, host_uuid)
            except exception.HostCpuDataNotFound:
                msg = _('host cpu data not found')
                raise webob.exc.HTTPBadRequest(explanation=msg)
        
        
        for host_uuid, vm_mrigation_list in vms_mrigation_selection:
            available_hosts = self._get_all_available_hosts(context)
            filter_scheduler_algorithms_fuctions = self._get_filter_scheduler_algorithms_in_use(context)
            available_filter_hosts = self._get_filter_hosts(available_hosts, filter_scheduler_algorithms_fuctions)
            
            """
            @@@@注：及时更新HostLoadState中的信息；
            """
            vm_host_mapper, vms_hosts_mapper_fales = host_scheduler_algorithm_fuction(
                                                            vm_mrigation_list, 
                                                            host_uuid, 
                                                            available_filter_hosts)
            """
            vms_hosts_mapper = {host_uuid1:{vm1:host1,vm2:host2,......}, 
                               host_uuid2:{vm3:host1,vm4:host2,......}, 
                               ......}
            """
            vms_hosts_mapper[host_uuid] = vm_host_mapper
            
            
        
        """
        实现相关虚拟机到目标主机的迁移操作；
        注：如果判断虚拟机迁移是否成功，估计要对nova和novaclient中的相关源码进行改进；
        """
        for host_uuid, vm_host_mapper in vms_hosts_mapper:
            for vm_uuid, host_uuid in vm_host_mapper:
                novaclient(context).servers.live_migrate(vm_uuid, host_uuid, False, False)
        
        """
        检测欠载的主机是否仍为欠载状态，将仍为欠载状态的主机上的所有虚拟机实例迁移出去，并设置
        主机为低功耗状态；
        """
        vms_underload_hosts_mapper = dict()
        for host_uuid in underload_hosts_uuid:
            try:
                host_load_states = self.hosts_api.get_host_load_states_by_id(context, host_uuid)
            except exception.NotFound:
                raise exc.HTTPNotFound()
            
            host_load_state = host_load_states['host_load_state']
            if host_load_state == 'underload':
                available_hosts = self._get_all_available_hosts(context)
                filter_scheduler_algorithms_fuctions = self._get_filter_scheduler_algorithms_in_use(context)
                available_filter_hosts = self._get_filter_hosts(available_hosts, filter_scheduler_algorithms_fuctions)
                
                """
                远程获取指定主机上所有的虚拟机实例；
                """
                vir_connection = libvirt.openReadOnly(host_uuid)
                vms_current = self._get_current_vms(vir_connection)
                
                vm_host_mapper = host_scheduler_algorithm_fuction(vms_current, 
                                                            available_filter_hosts)
                vms_underload_hosts_mapper[host_uuid] = vm_host_mapper
        
        
        """
        实现相关虚拟机到目标主机的迁移操作；
        注：如果判断虚拟机迁移是否成功，估计要对nova和novaclient中的相关源码进行改进；
        """
        for uuid, vm_host_mapper in vms_underload_hosts_mapper:
            for vm_uuid, host_uuid in vm_host_mapper:
                novaclient(context).servers.live_migrate(vm_uuid, host_uuid, False, False)
        
        """
        实现欠载主机的虚拟机迁移操作之后，设置其运行状态为低功耗模式；
        """
        sleep_command = CONF.sleep_command
        for uuid, vm_host_mapper in vms_underload_hosts_mapper:
            try:
                self.controller_rpcapi.switch_host_off(context, sleep_command, uuid, controller_topic)
            except exception.DataCollectionError:
                msg = _('There are some error in hosts and vms data collection operation.')
                raise webob.exc.HTTPBadRequest(explanation=msg)
        
        time.sleep(CONF.wait_time)
    
    
    def _get_all_available_hosts(self, context):
        hosts_api = hosts.API()
        hosts = novaclient(context).hosts.index()
        hosts_states = hosts_api.get_all_hosts_load_states_sorted_list(context)
        hosts_temp = list()
        
        for uuid, host_load_state in hosts_states:
            if host_load_state == 'normalload' or 'underload':
                hosts_temp.add(uuid)
                
        for i in hosts_temp:
            if i not in hosts['id']:
                del hosts_temp[i]
        
        available_hosts = hosts_temp
        
        return available_hosts
    
    def _get_filter_scheduler_algorithms_in_use(self, context):
        hosts_api = hosts.API()
        filter_scheduler_algorithms_fuctions = list()
        
        filter_scheduler_algorithms_names = hosts_api.get_filter_scheduler_algorithms_in_used(context)
        
        for algorithm_name in filter_scheduler_algorithms_names:
            algorithm_fuction = CONF.filter_scheduler_algorithm_path + '.' + algorithm_name
            filter_scheduler_algorithms_fuctions.add(algorithm_fuction)
            
        return filter_scheduler_algorithms_fuctions
    
    def _get_filter_hosts(self, host_list, filter_scheduler_algorithms_fuctions):
        for algorithm_fuction in filter_scheduler_algorithms_fuctions:
            host_list = filter_scheduler_algorithms_fuctions(host_list)
            
    def _get_current_vms(self, vir_connection):
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
    
    def init_host(self):
        """
        调用获取算法API，如果返回值为空，从配置文件读取算法信息，写入数据库；        
        """
        context = xdrs.context.get_admin_context()
        
        try:
            algorithm = self.hosts_api.get_all_algorithms_sorted_list(context)
        except exception.AlgorithmsNotFound:
            msg = _('algorithms not found')
            raise webob.exc.HTTPBadRequest(explanation=msg)
        
        """
        FilterSchedulerAlgorithms
        OverloadAlgorithms
        UnderloadAlgorithms
        HostSchedulerAlgorithms
        VmSelectAlgorithms
        filter_scheduler_algorithm_list = [
            {algorithm_name:XXXX,
             algorithm_para:XXXX,
             algorithm_inuse:True},
            {algorithm_name:XXXX,
             algorithm_para:XXXX,
             algorithm_inuse:False},
            {algorithm_name:XXXX,
             algorithm_para:XXXX,
             algorithm_inuse:False}]
        """
        if algorithm is None:
            filter_scheduler_algorithm_list = CONF.filter_scheduler_algorithm_list
            overload_algorithm_list = CONF.overload_algorithm_list
            underload_algorithm_list = CONF.underload_algorithm_list
            host_scheduler_algorithm_list = CONF.host_scheduler_algorithm_list
            vm_select_algorithm_list = CONF.vm_select_algorithm_list
            
            for filter_scheduler_algorithm in filter_scheduler_algorithm_list:
                algorithm_id = random.randint(0, 0xffffffffffffffff)
                filter_scheduler_algorithm['algorithm_id'] = algorithm_id
                
                try:
                    algorithm = self.hosts_api.create_filter_scheduler_algorithm(context, filter_scheduler_algorithm)
                except exception.AlgorithmNotFound as ex:
                    raise webob.exc.HTTPNotFound(explanation=ex.format_message())
            
            for overload_algorithm in overload_algorithm_list:
                algorithm_id = random.randint(0, 0xffffffffffffffff)
                overload_algorithm['algorithm_id'] = algorithm_id
                
                try:
                    algorithm = self.hosts_api.create_overload_algorithm(context, overload_algorithm)
                except exception.AlgorithmNotFound as ex:
                    raise webob.exc.HTTPNotFound(explanation=ex.format_message())
            
            for underload_algorithm in underload_algorithm_list:
                algorithm_id = random.randint(0, 0xffffffffffffffff)
                underload_algorithm['algorithm_id'] = algorithm_id
                
                try:
                    algorithm = self.hosts_api.create_underload_algorithm(context, underload_algorithm)
                except exception.AlgorithmNotFound as ex:
                    raise webob.exc.HTTPNotFound(explanation=ex.format_message())
            
            for host_scheduler_algorithm in host_scheduler_algorithm_list:
                algorithm_id = random.randint(0, 0xffffffffffffffff)
                host_scheduler_algorithm['algorithm_id'] = algorithm_id
                
                try:
                    algorithm = self.hosts_api.create_host_scheduler_algorithm(context, host_scheduler_algorithm)
                except exception.AlgorithmNotFound as ex:
                    raise webob.exc.HTTPNotFound(explanation=ex.format_message())
            
            for vm_select_algorithm in vm_select_algorithm_list:
                algorithm_id = random.randint(0, 0xffffffffffffffff)
                vm_select_algorithm['algorithm_id'] = algorithm_id
                
                try:
                    algorithm = self.hosts_api.create_vm_select_algorithm(context, vm_select_algorithm)
                except exception.AlgorithmNotFound as ex:
                    raise webob.exc.HTTPNotFound(explanation=ex.format_message())