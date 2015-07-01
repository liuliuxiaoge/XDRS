"""
The vm cpu data API extension.
虚拟机示例CPU数据的相关API的扩展；
"""

import webob
from webob import exc

from xdrs.api.v1.admin_detection import authorize
from xdrs.api.openstack import extensions
from xdrs.api.openstack import wsgi
from xdrs import hosts
from xdrs import exception
from xdrs.openstack.common.gettextutils import _
from xdrs.openstack.common import log as logging

LOG = logging.getLogger(__name__)


def _translate_vm_cpu_data_detail_view(context, vm_cpu_data):
    """
    Maps keys for vm cpu data details view.
    """

    d = _translate_vm_cpu_data_summary_view(context, vm_cpu_data)

    # No additional data / lookups at the moment

    return d


def _translate_vm_cpu_data_summary_view(context, vm_cpu_data):
    """
    Maps keys for vm cpu data summary view.
    """
    d = {}

    d['vm_id'] = vm_cpu_data['vm_id']
    d['host_id'] = vm_cpu_data['host_id']
    d['host_name'] = vm_cpu_data['host_name']
    d['data_len'] = vm_cpu_data['data_len']
    d['cpu_data'] = vm_cpu_data['cpu_data']
    LOG.audit(_("vm_cpu_data=%s"), vm_cpu_data, context=context)

    return d



class VMsCpuDataController(wsgi.Controller):
    """
    The vm cpu data API controller for the OpenStack API.
    """
    
    def __init__(self, **kwargs):
        super(VMsCpuDataController, self).__init__(**kwargs)
        self.hosts_api = hosts.API()
    
    def get_vm_cpu_data_by_host_id(self, req, id):
        context = req.environ['xdrs.context']
        authorize(context, 'get_vm_cpu_data')
        
        try:
            vms_cpu_data = self.hosts_api.get_vm_cpu_data_by_host_id(context, id)
        except exception.NotFound:
            raise exc.HTTPNotFound()
        
        vms_cpu_data_dict = self._items(req, context, vms_cpu_data, entity_maker=_translate_vm_cpu_data_detail_view)
        
        return vms_cpu_data_dict
        
    
    def _items(self, context, vms_cpu_data, entity_maker):
        """
        Returns a list of vms cpu data, transformed through entity_maker.
        """
        vms_cpu_data = [entity_maker(context, vm_cpu_data) for vm_cpu_data in vms_cpu_data]
        return {'vms_cpu_data': vms_cpu_data}
        
        
    def get_vm_cpu_data_by_vm_id(self, req, id):
        context = req.environ['xdrs.context']
        authorize(context, 'get_vm_cpu_data')
        
        try:
            vm_cpu_data = self.hosts_api.get_vm_cpu_data_by_vm_id(context, id)
        except exception.NotFound:
            raise exc.HTTPNotFound()
        
        vm_cpu_data = _translate_vm_cpu_data_detail_view(context, vm_cpu_data)
        vm_cpu_data_dict = {'vm_cpu_data':vm_cpu_data}
        
        return vm_cpu_data_dict
        
    def delete_vm_cpu_data_by_host_id(self, req, id):
        """
        注：这个方法需要比较细致地来写；
        """
        context = req.environ['xdrs.context']
        authorize(context, 'destroy_vm_cpu_data')
        
        try:
            vms_cpu_data = self.hosts_api.delete_vm_cpu_data_by_host_id(context, id)
        except exception.NotFound:
            raise exc.HTTPNotFound()
        return webob.Response(status_int=202)
        
        
    def delete_vm_cpu_data_by_vm_id(self, req, id):
        """
        注：这个方法需要比较细致地来写；
        """
        context = req.environ['xdrs.context']
        authorize(context, 'destroy_vm_cpu_data')
        
        try:
            vm_cpu_data = self.hosts_api.delete_vm_cpu_data_by_vm_id(context, id)
        except exception.NotFound:
            raise exc.HTTPNotFound()
        return webob.Response(status_int=202)


class SpecificVmsCpuData(extensions.ExtensionDescriptor):
    name = "Specific Vms Cpu Data"
    alias = "os-vms-cpu-data"
    namespace = " "
    updated = "2015-03-25T00:00:00+00:00"

    def get_resources(self):
        resources = []
        res = extensions.ResourceExtension(
                 'os-vms-cpu-data',
                 VMsCpuDataController(),
                 member_actions={
                     'get_vm_cpu_data_by_host_id':'GET',
                     'get_vm_cpu_data_by_vm_id':'GET',
                     'delete_vm_cpu_data_by_host_id':'DELETE',
                     'delete_vm_cpu_data_by_vm_id':'DELETE',
                  }
               )
        resources.append(res)
        return resources