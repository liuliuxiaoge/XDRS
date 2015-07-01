"""
1.如何判断操作为API还是LocalAPI；
2.入口：
  def _schedule(self, context, request_spec, filter_properties, instance_uuids=None)
其中：
context：上下文环境；
request_spec：建立虚拟机实例的需求信息（注：在nova之中，这个方法同时实现了虚拟机建立的其他
步骤，所以在借鉴这个方法的同时要注意做好取舍）；
filter_properties：虚拟机过滤条件；
instance_uuids：要建立的虚拟机的uuid值；
"""
import os
import sys

from oslo.config import cfg

filter_scheduler_opts = [
    cfg.IntOpt('scheduler_host_subset_size',
               default=1,
               help='New instances will be scheduled on a host chosen '
                    'randomly from a subset of the N best hosts. This '
                    'property defines the subset size that a host is '
                    'chosen from. A value of 1 chooses the '
                    'first host returned by the weighing functions. '
                    'This value must be at least 1. Any value less than 1 '
                    'will be ignored, and 1 will be used instead')
]

CONF = cfg.CONF
CONF.register_opts(filter_scheduler_opts)


def _schedule(self, context, request_spec, filter_properties,
              instance_uuids=None):
    """
    Returns a list of hosts that meet the required specs,
    ordered by their fitness.
    获取所有满足所需规格的主机列表；
    注：在xdrs中context、request_spec和filter_properties是必需的；
        
    @@@@注：
    1.context需要详细从nova中解析引用过来；
    2.request_spec需要详细从nova中解析引用过来；
    3.filter_properties需要按照nova中的格式进行书写；
    """
    """
    返回具有管理员用户的上下文权限；
    """
    elevated = context.elevated()
    instance_properties = request_spec['instance_properties']
    instance_type = request_spec.get("instance_type", None)
        
    """
    更新filter_properties中的group相关属性信息；
    """
    update_group_hosts = self._setup_instance_group(context,
            filter_properties)

    """
    用于测试，这条语句可以考虑删除（还需要进一步验证）；
    """
    config_options = self._get_configuration_options()

    properties = instance_properties.copy()
    if instance_uuids:
        properties['uuid'] = instance_uuids[0]
    self._populate_retry(filter_properties, properties)

    """
    更新过滤器属性信息filter_properties；
    """
    filter_properties.update({'context': context,
                             'request_spec': request_spec,
                             'config_options': config_options,
                             'instance_type': instance_type})

    self.populate_filter_properties(request_spec,
                                   filter_properties)

    hosts = self._get_all_host_states(elevated)

    selected_hosts = []
    if instance_uuids:
        num_instances = len(instance_uuids)
    else:
        num_instances = request_spec.get('num_instances', 1)
    for num in xrange(num_instances):
        hosts = self.host_manager.get_filtered_hosts(hosts,
                filter_properties, index=num)
        if not hosts:
            # Can't get any more locally.
            break

        weighed_hosts = self.host_manager.get_weighed_hosts(hosts,
                filter_properties)

        scheduler_host_subset_size = CONF.scheduler_host_subset_size
        if scheduler_host_subset_size > len(weighed_hosts):
            scheduler_host_subset_size = len(weighed_hosts)
        if scheduler_host_subset_size < 1:
            scheduler_host_subset_size = 1

        chosen_host = random.choice(
            weighed_hosts[0:scheduler_host_subset_size])
        selected_hosts.append(chosen_host)

        # Now consume the resources so the filter/weights
        # will change for the next instance.
        chosen_host.obj.consume_from_instance(instance_properties)
        if update_group_hosts is True:
            filter_properties['group_hosts'].add(chosen_host.obj.host)
    return selected_hosts