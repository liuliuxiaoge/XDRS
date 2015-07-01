"""
实现选取合适的目标主机用于vms的迁移操作，特点是多个vms迁移到一个或几个主机上，
以实现用户的某些特定场景，对应于vm迁移的单选算法；
"""

import webob

from xdrs import hosts
from xdrs import exception
from oslo.config import cfg
from random import choice
import libvirt

CONF = cfg.CONF
CONF.import_opt('host_cpu_usable_by_vms', 'xdrs.service')
CONF.import_opt('overload_algorithm_path', 'xdrs.service')
CONF.import_opt('underload_algorithm_path', 'xdrs.service')

def multiple_hosts_select(context, vms_list, local_host_uuid, hosts_list):
    """
    实现选取合适的目标主机用于vms的迁移操作，特点是多个vms迁移到一个或几个主机上，
    以实现用户的某些特定场景，对应于vm迁移的单选算法；
    参数：
    context：上下文环境信息；
    vms_list：所有要执行迁移操作的vm列表；
    hosts_list：经过前期过滤的所有被选主机列表；
    local_host_uuid：本地主机的uuid；
    输出：
    字典：hosts_select(host,list(vms))
    vms：没有合适目标主机的虚拟机实例列表；
    """
    
    """
    1 获取所有要迁移虚拟机（vms_list）的RAM和CPU使用相关数据；
    """
    vms_cpu_data, vms_ram_data = _get_vms_statics(context, vms_list, local_host_uuid)
    
    """  
    2 获取所有主机的可用ram和CPU相关数据； 
    注：这里的hosts_cpu_data是通过get_host_cpu_data_temp_by_id获取，
    从HostCpuDataTemp数据表获取；
    """
    hosts_cpu_data, hosts_total_ram, hosts_free_ram = _get_hosts_statics(context, hosts_list)
    
    """
    3 计算所有vms_list的总的ram大小；
      说明：vms_ram_total；
    """
    vms_ram_total = 0
    for vm in vms_list:
        vms_ram_total = vms_ram_total+vms_ram_data[vm]
    
    """
    4 多主机选取算法主体；
      说明：def _multiple_hosts_select
      输入：
      vms_list：要迁移的虚拟机列表；
      hosts_list：备选主机列表；
      输出：
      vm_noselect_list_finally：未选取到合适主机的虚拟机列表；
      hosts_select_finally：已选取的主机虚拟机映射字典，其格式为(host1:vms_list1,host2:vms_list2......)；
    """
    _multiple_hosts_select(
        context, 
        vms_list, 
        local_host_uuid, 
        hosts_list, 
        vms_cpu_data, 
        vms_ram_data, 
        hosts_cpu_data, 
        hosts_total_ram, 
        hosts_free_ram, 
        vms_ram_total)

def _get_vms_statics(context, vms_list, host_uuid):
    """
    获取所有要迁移虚拟机（vms_list）的RAM和CPU使用相关数据；
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
    
    return vms_cpu_data, vms_ram_data
    


def _get_hosts_statics(context, hosts_list):
    """
    获取所有主机的可用ram和CPU相关数据； 
    注：这里的hosts_cpu_data是通过get_host_cpu_data_temp_by_id获取，
    从HostCpuDataTemp数据表获取；
    """
    hosts_api = hosts.API()
    
    hosts_cpu_data = dict()
    hosts_total_ram = dict()
    hosts_free_ram = dict()
    for host in hosts_list:
        try:
            cpu_data = hosts_api.get_host_cpu_data_temp_by_id(context, host)
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
    
    return hosts_cpu_data, hosts_total_ram, hosts_free_ram

def _multiple_hosts_select(
        context, 
        vms_list, 
        local_host_uuid, 
        hosts_list, 
        vms_cpu_data, 
        vms_ram_data, 
        hosts_cpu_data, 
        hosts_total_ram, 
        hosts_free_ram, 
        vms_ram_total):
    """
    多主机选取算法主体；
    参数：
    context：上下文环境信息；
    local_host_uuid：本地主机uuid；
    vms_list：要迁移的虚拟机列表；
    hosts_list：备选主机列表；
    vms_cpu_data：相关虚拟机实例的CPU数据；
    vms_ram_data：相关虚拟机实例的RAM数据；
    hosts_cpu_data：相关备选主机的CPU数据；
    hosts_total_ram：相关备选主机的总的RAM信息；
    hosts_free_ram：相关备选主机的空闲RAM信息；
    vms_ram_total：要迁移的虚拟机实例的总的RAM大小；
    """
    """
    1 根据vms_list_0从_get_vms_statics中获取ram/cpu数据；
      根据vms_list_0计算vms_list_0总的ram大小；
      根据hosts_list_0从hosts_space_statics中获取ram_space/cpu_data数据；
    """
    hosts_api = hosts.API()
    vms_list_global = vms_list
    host_noselect_list_global = hosts_list
    
    for host_uuid in hosts_list:
        host_init_data_create = dict()
        try:
            host_init_data = hosts_api.get_host_init_data(context, host_uuid)
        except exception.HostInitDataNotFound:
            msg = _('host init data not found')
            raise webob.exc.HTTPBadRequest(explanation=msg)
        
        host_init_data_create['previous_host_cpu_time_total'] =  \
            host_init_data['previous_host_cpu_time_total']
        host_init_data_create['previous_host_cpu_time_busy'] = \
            host_init_data['previous_host_cpu_time_busy']
        host_init_data_create['physical_cpu_mhz'] = \
            host_init_data['physical_cpu_mhz']
        host_init_data_create['host_uuid'] = \
            host_init_data['host_uuid']
        
        try:
            host_init_data = hosts_api.create_host_init_data_temp(context, host_init_data_create)
        except exception.HostInitDataNotFound:
            msg = _('host init data not found')
            raise webob.exc.HTTPBadRequest(explanation=msg)
    """
    2 循环遍历hosts_list_0，验证hosts_list_0中的主机是否满足虚拟机实例总的ram大小；
      说明：从配置文件读取ram上限百分比和disk上限百分比的参数值；
    """
    ram_distance = dict()
    for host_uuid in hosts_list:
        ram_distance[host_uuid] = hosts_free_ram[host_uuid]-vms_ram_total
        if hosts_free_ram[host_uuid] <= vms_ram_total:
            del hosts_list[host_uuid]
    
    """
    3 如果有满足条件的host存在，存储到hosts_select_0中，hosts_select_0为(host,vms_list)格式；
    """
    hosts_select_0 = dict()
    if hosts_list is not None:
        for host_uuid in hosts_list:
            hosts_select_0[host_uuid] = vms_list
    
    """
    4 如果没有满足条件的host存在，判断不满足的原因，并采取相应的方法去除若干vms，直到主机
      满足条件；
      （1）判断不满足的原因RAM_NOENOUGH（内存不满足）,获取此种情况下与需求差距
           最小的主机min_ram_distance_host；
      （2）采取随机选取的方法去除若干vms，直到主机满足条件（这里也许是一个改进的地方）；
      def _host_ram_not_enough_process
      输入：min_ram_distance_host；
            vms_list_0：要迁移的虚拟机列表；
            vms_statics（vms_list_0）：要迁移虚拟机列表数据信息字典；
      输出：hosts_select_1，hosts_select_1为(host,vms_list)格式，表示经过减去若干虚拟机实例
            从而获取到可以作为部分虚拟机实例迁移目标的最合适主机（暂时第一阶段）；
    """
    if hosts_list == None:
        vms_select_temp, min_ram_distance_host = _host_ram_not_enough_process(
                                                   context, 
                                                   ram_distance, 
                                                   vms_list, 
                                                   vms_ram_data)
        hosts_select_1 = {min_ram_distance_host: vms_select_temp}
    
    """
    5 如果hosts_select_0和hosts_select_1均为空，说明群选算法失败，直接返回；
    """
    if hosts_select_0 is None and hosts_select_1 is None:
        return False
    
    """
    6 将不为空的hosts_select_0或hosts_select_1赋值给hosts_select_2；
      hosts_select_0和hosts_select_1不可能同时为真；
    """
    hosts_select_2 = dict()
    if hosts_select_0 is not None:
        hosts_select_2 = hosts_select_0
    else:
        if hosts_select_1 is not None:
            hosts_select_2 = hosts_select_1
    
    """
    7 针对hosts_select_2，格式为(host1:vms_list1,host2:vms_list2......),对于每个备选主机，都
      要进行预迁移的CPU利用率计算，判断每一个主机完成虚拟机迁移操作之后的运行状态，即欠载还是负载；
      注：之所以有host1/host2/......等之分，是因为hosts_select_0中可能同时有多个主机满足条件，而
          针对hosts_select_1，只能有一个满足条件的主机；
      def _migrate_host_cpu_predict
      输入：hosts_select_2，格式为(host1:vms_list1,host2:vms_list1......)；
      输出：host_cpu_predict，格式为(host1:(state,CPU利用率),host2:(state,CPU利用率)......)；
    """
    overload_algorithm = hosts_api.get_overload_algorithm_in_used(context)
    overload_algorithm_name = overload_algorithm['algorithm_name']
    overload_algorithm_params = overload_algorithm['algorithm_params']
    overload_algorithm_fuction = CONF.overload_algorithm_path + '.' + overload_algorithm_name
    overload_algorithm_fuction_params = [overload_algorithm_params]
    
    underload_algorithm = hosts_api.get_underload_algorithm_in_used(context)
    underload_algorithm_name = underload_algorithm['algorithm_name']
    underload_algorithm_params = underload_algorithm['algorithm_params']
    underload_algorithm_fuction = CONF.underload_algorithm_path + '.' + underload_algorithm_name
    underload_algorithm_fuction_params = [underload_algorithm_params]
    
    host_cpu_predict = dict()
    host_cpu_predict_underload = dict()
    host_cpu_predict_overload = dict()
    host_cpu_predict_normalload = dict()
    for host_uuid_temp, vms_list_temp in hosts_select_2:
        for vm in vms_list_temp:
            vir_connection = libvirt.openReadOnly(host_uuid_temp)
            physical_cpu_mhz_total = int(_physical_cpu_mhz_total(vir_connection) *
                                            float(CONF.host_cpu_usable_by_vms))
            
            host_cpu_utilization = _vm_mhz_to_percentage(
                    vms_cpu_data[vm],
                    hosts_cpu_data[host_uuid_temp],
                    physical_cpu_mhz_total)
        
        """
        调用确定的欠载检测算法进行主机的欠载检测；
        """
        underload, underload_detection_state = \
            underload_algorithm_fuction(host_cpu_utilization, underload_algorithm_fuction_params)
        
        """
        调用确定的过载检测算法进行主机的过载检测；
        """
        overload, overload_detection_state = \
            overload_algorithm_fuction(host_cpu_utilization, overload_algorithm_fuction_params)
        
        if underload is True:
            load_state = 'underload'
        if overload is True:
            load_state = 'overload'
        if underload is False and overload is False:
            load_state = 'normalload'
        
        host_cpu_predict[host_uuid_temp] = (load_state, host_cpu_utilization, vms_list_temp)
        if load_state == 'underload':
            host_cpu_predict_underload[host_uuid_temp] = (host_cpu_utilization, vms_list_temp)
        if load_state == 'overload':
            host_cpu_predict_overload[host_uuid_temp] = (host_cpu_utilization, vms_list_temp)
        if load_state == 'normalload':
            host_cpu_predict_normalload[host_uuid_temp] = (host_cpu_utilization, vms_list_temp)
    """
    8 针对返回值host_cpu_predict，根据其中state的不同，分别赋值给host_cpu_predict_underload和host_cpu_predict_overload
      和host_cpu_predict_normalload；
      host_cpu_predict_underload：格式为(host1:(vms_list1,CPU利用率),host2:(vms_list1,CPU利用率)......)
    """
    """
    9 针对host_cpu_predict_normalload：格式为(host1:(vms_list1,CPU利用率),host2:(vms_list2,CPU利用率)......)
      （1）如果host_cpu_predict_normalload中只有一个元素，说明在进行主机预迁移的CPU利用率计算之后，只有
           一个主机处于正常负载状态，则直接添加到变量hosts_select_finally中；
           hosts_select_finally格式为(host1:vms_list1,host2:vms_list2......)；
      （2）如果host_cpu_predict_normalload中有多个元素，说明在进行主机预迁移的CPU利用率计算之后，有
           多个主机处于正常负载状态，则选取CPU利用率最小的一个，添加到变量hosts_select_finally中；
    """
    hosts_select_finally = dict()
    if len(host_cpu_predict_normalload) == 1:
        for host_uuid, values in host_cpu_predict_normalload:
            vms_list = values[1]
            hosts_select_finally[vms_list] = host_uuid
    
    if len(host_cpu_predict_normalload) > 1:
        host_cpu_utilization_sort = sorted(host_cpu_predict_normalload.iteritems(), key=lambda d:d[2], reverse = False)
        min_host_cpu_utilization = host_cpu_utilization_sort[0]
        vm_list = min_host_cpu_utilization[1]
        host_uuid = min_host_cpu_utilization[0]
        hosts_select_finally[vm_list] = host_uuid
      
    """
    10 如果host_cpu_predict_underload和host_cpu_predict_normalload为空，且host_cpu_predict_overload不为空，
       则说明在进行主机预迁移的CPU利用率计算之后，所有主机均处于过载状态；
       如果host_cpu_predict_overload中的元素只有一个，则直接赋值给hosts_select_3；
       如果host_cpu_predict_overload中的元素大于一个，则选取所有主机中CPU利用率最小的一个赋值给
       hosts_select_3；
    """
    hosts_select_3 = dict()
    if host_cpu_predict_underload is None and \
        host_cpu_predict_normalload is None and \
            host_cpu_predict_overload is not None:
        if len(host_cpu_predict_overload) == 1:
            for host_uuid, values in host_cpu_predict_overload:
                vms_list = values[1]
                hosts_select_3[vms_list] = host_uuid
        
        if len(host_cpu_predict_overload) > 1:
            host_cpu_utilization_sort = sorted(host_cpu_predict_overload.iteritems(), key=lambda d:d[2], reverse = False)
            min_host_cpu_utilization = host_cpu_utilization_sort[0]
            vm_list = min_host_cpu_utilization[1]
            host_uuid = min_host_cpu_utilization[0]
            hosts_select_3[vm_list] = host_uuid
    
    """
    11 如果host_cpu_predict_normalload为空，且host_cpu_predict_underload和host_cpu_predict_overload不为空：
       （1）如果host_cpu_predict_underload中只有一个元素，说明说明在进行主机预迁移的CPU利用率计算之后，只有
            一个主机处于欠载状态，其余全部处于过载状态，则直接添加到变量hosts_select_finally中，并进行标注，
            此主机虽然迁移过后仍处于欠载状态，但是后续不可以进行虚拟机全部迁移出去的操作。
       （2）如果host_cpu_predict_underload中有多个元素，则选取利用率最大的主机作为目标主机，直接添加到变量
            hosts_select_finally中；
    """
    if host_cpu_predict_normalload is None and \
        host_cpu_predict_underload is not None and \
            host_cpu_predict_overload is not None:
        if len(host_cpu_predict_underload) == 1:
            for host_uuid, values in host_cpu_predict_underload:
                vms_list = values[1]
                hosts_select_finally[vms_list] = host_uuid
        
        if len(host_cpu_predict_underload) > 1:
            host_cpu_utilization_sort = sorted(host_cpu_predict_underload.iteritems(), key=lambda d:d[2], reverse = True)
            min_host_cpu_utilization = host_cpu_utilization_sort[0]
            vm_list = min_host_cpu_utilization[1]
            host_uuid = min_host_cpu_utilization[0]
            hosts_select_finally[vm_list] = host_uuid
    
    """
    12 针对hosts_select_3中所指定的主机（主要在10中产生），循环减去其对应的vms_list中最耗费CPU资源的vm，直到满足主机
       的CPU利用率处于正常状态为止；
       def _host_CPU_overload_process
       输入：hosts_select_3，格式为(host:(vms_list,CPU利用率))；
       输出：hosts_select_4，格式为(host:(vms_list,CPU利用率))；
    """
    hosts_select_4 = _host_cpu_overload_process(
                        context, 
                        hosts_select_3, 
                        vms_cpu_data, 
                        hosts_cpu_data)
    """
    13 将hosts_select_4添加到变量hosts_select_finally之中，至此完成第一轮选取；
    """
    hosts_select_finally = hosts_select_4
    
    """
    14 确定此时尚未确定迁移目标的虚拟机实例列表vm_noselect_list；
       确定此时虚拟机实例迁移备用目标主机host_noselect_list，要根据第一轮的选择进行相应主机资源利用信息的数据库更新；
    """
    vms_ram_total_temp = 0
    for host_uuid, vm_list_temp in hosts_select_finally:
        for vm in vm_list_temp:
            vms_ram_total_temp = vms_ram_total_temp+vms_ram_data[vm]
        
        
        try:
            host_cpu_data_temp = hosts_api.get_host_cpu_data_temp_by_id(context, host_uuid)
        except exception.HostCpuDataNotFound:
            msg = _('host cpu data not found')
            raise webob.exc.HTTPBadRequest(explanation=msg)
        
        host_cpu_data_temp['hosts_free_ram'] = host_cpu_data_temp['hosts_free_ram'] - vms_ram_total_temp
        
        try:
            cpu_data = hosts_api.update_host_cpu_data_temp_by_id(context, host_cpu_data_temp, host_uuid)
        except exception.HostCpuDataNotFound:
            msg = _('host cpu data not found')
            raise webob.exc.HTTPBadRequest(explanation=msg)
        
        vm_noselect_list = vms_list_global-vm_list_temp
        host_noselect_list = host_noselect_list_global.delete(host_uuid)
    """
    15 判断此时vm_noselect_list是否为空，
       （1）如果vm_noselect_list为空，说明所有虚拟机实例均找到合适的目标主机；
            则直接跳出循环；
       （2）如果vm_noselect_list不为空，比较vm_noselect_list与全局变量vm_noselect_list_global,
            如果vm_noselect_list与vm_noselect_list_global的值相同，说明此轮主机选取操作没有为
            任何vm寻找到合适的迁移目标主机，则直接跳出循环；
       （3）如果vm_noselect_list不为空，比较vm_noselect_list与全局变量vm_noselect_list_global,
            如果vm_noselect_list与vm_noselect_list_global的值不同，说明尚有部分vms没有找到合适
            的迁移目标主机，则：
            a 赋值vm_noselect_list给vm_noselect_list_global；
            b 迭代调用方法def _multiple_hosts_select
              输入：
              vm_noselect_list：此轮要迁移的虚拟机列表；
              host_noselect_list：此轮备选主机列表；
    """
    while vm_noselect_list:
        if vm_noselect_list is None:
            break
        vm_noselect_list_global = vm_noselect_list
        
        hosts_cpu_data, hosts_total_ram, hosts_free_ram = _get_hosts_statics(context, host_noselect_list)
        vms_cpu_data, vms_ram_data = _get_vms_statics(context, vm_noselect_list, local_host_uuid)
        vms_ram_total = 0
        for vm in vm_noselect_list:
            vms_ram_total = vms_ram_total+vms_ram_data[vm]
        
        _multiple_hosts_select(
            context, 
            vm_noselect_list, 
            local_host_uuid, 
            host_noselect_list, 
            vms_cpu_data, 
            vms_ram_data, 
            hosts_cpu_data, 
            hosts_total_ram, 
            hosts_free_ram, 
            vms_ram_total)
        
        if vm_noselect_list is not None:
            if vm_noselect_list == vm_noselect_list_global:
                break
    
    """
    16 确定最后无法选取合适主机的虚拟机列表vm_noselect_list_finally；
    17 确定最后完成选取的主机和虚拟机的映射字典hosts_select_finally，其格式为(host1:vms_list1,host2:vms_list2......)；
    """
    for host_uuid_select, vm_list_select in hosts_select_finally:
        vm_noselect_list_finally = vms_list_global-vm_list_select
        
    return hosts_select_finally, vm_noselect_list_finally


def _host_ram_not_enough_process(
        context, 
        ram_distance, 
        vms_list, 
        vms_ram_data):
    """
    没有满足条件的host存在的情况下调用此方法，采取相应的方法去除若干vms，直到主机
    满足条件；
    （1）判断不满足的原因RAM_NOENOUGH（内存不满足）,获取此种情况下与需求差距
         最小的主机min_ram_distance_host；
    （2）采取随机选取的方法去除若干vms，直到主机满足条件（这里也许是一个改进的地方）；
    """
    
    min_ram_distance = 0
    ram_distance_list = sorted(ram_distance.iteritems(), key=lambda d:d[1], reverse = True)
    min_ram_distance = ram_distance_list[0]
        
    min_ram_distance_host = min_ram_distance[0]
    min_ram_distance_value = min_ram_distance[1]
    
    vms_ram_sum = 0
    vms_select_temp = list()
    while vms_ram_sum < min_ram_distance_value:
        vm = choice(vms_list)
        vms_ram_sum = vms_ram_sum + vms_ram_data[vm]
        vms_select_temp = vms_list.delete(vm)
    
    return vms_select_temp, min_ram_distance_host

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

def _host_cpu_overload_process(context, hosts_select_3, vms_cpu_data, hosts_cpu_data):
    hosts_api = hosts.API()
    
    hosts_select_4 = dict()
    overload_algorithm = hosts_api.get_overload_algorithm_in_used(context)
    overload_algorithm_name = overload_algorithm['algorithm_name']
    overload_algorithm_params = overload_algorithm['algorithm_params']
    overload_algorithm_fuction = CONF.overload_algorithm_path + '.' + overload_algorithm_name
    overload_algorithm_fuction_params = [overload_algorithm_params]
    
    for host_uuid, vm_list_temp in hosts_select_3:
        vir_connection = libvirt.openReadOnly(host_uuid)
        physical_cpu_mhz_total = int(_physical_cpu_mhz_total(vir_connection) *
                                            float(CONF.host_cpu_usable_by_vms))
        overload = True
        while overload:
            vm = choice(vm_list_temp)
            vm_list_temp.delete(vm)
            for vm in vm_list_temp:
                host_cpu_utilization = _vm_mhz_to_percentage(
                    vms_cpu_data[vm],
                    hosts_cpu_data[host_uuid],
                    physical_cpu_mhz_total)
                """
                调用确定的过载检测算法进行主机的过载检测；
                """
                overload, overload_detection_state = \
                    overload_algorithm_fuction(host_cpu_utilization, overload_algorithm_fuction_params)
        
        hosts_select_4[host_uuid] = vm_list_temp
    
    return hosts_select_4

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
    
    mhz_history = [[0] * (max_len - len(x)) + x
                   for x in vm_mhz_history + [host_mhz_history]]
    return [float(sum(x)) / physical_cpu_mhz for x in zip(*mhz_history)]

def _compute_host_cpu_mhz(context, host_uuid_temp):
    hosts_api = hosts.API()
    
    try:
        host_init_data = hosts_api.compute_host_cpu_mhz(context, host_uuid_temp)
    except exception.HostInitDataNotFound:
        msg = _('host init data not found')
        raise webob.exc.HTTPBadRequest(explanation=msg)