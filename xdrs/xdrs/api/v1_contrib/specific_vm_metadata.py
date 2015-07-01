"""
The vm metadata API extension.
虚拟机实例元数据API相关扩展；
"""

import webob
from webob import exc

from xdrs.api.v1.admin_detection import authorize
from xdrs.api.openstack import extensions
from xdrs.api.openstack import wsgi
from xdrs import vms
from xdrs import exception
from xdrs import states
from xdrs.openstack.common.gettextutils import _
from xdrs.openstack.common import log as logging

LOG = logging.getLogger(__name__)


class VmMetadataController(wsgi.Controller):
    def __init__(self, **kwargs):
        super(VmMetadataController, self).__init__(**kwargs)
        self.vms_api = vms.API()  
        
    def get_vm_task_state_by_id(self, req, id):
        context = req.environ['xdrs.context']
        authorize(context, 'get_vm_task_state')
        
        try:
            vm_task_state = self.vms_api.get_vm_task_state_by_id(context, id)
        except exception.NotFound:
            raise exc.HTTPNotFound()
        
        if vm_task_state not in [states.VM_MIGRATING, 
                         states.VM_NORMAL]:
            msg = _('vm task state info is error!')
            raise webob.exc.HTTPBadRequest(explanation=msg)
           
        return vm_task_state
           
    def delete_vm_metadata_by_id(self, req, id):
        """
        注：这个方法需要比较细致地来写；
        """
        context = req.environ['xdrs.context']
        authorize(context, 'destroy_vm_cpu_data')
        
        try:
            vm_cpu_data = self.vms_api.delete_vm_metadata_by_id(context, id)
        except exception.NotFound:
            raise exc.HTTPNotFound()
        return webob.Response(status_int=202)


class SpecificVmMetadata(extensions.ExtensionDescriptor):
    name = "Specific Vms Cpu Data"
    alias = "os-vm-metadata"
    namespace = " "
    updated = "2015-03-25T00:00:00+00:00"

    def get_resources(self):
        resources = []
        res = extensions.ResourceExtension(
                 'os-vm-metadata',
                 VmMetadataController(),
                 member_actions={
                     'get_vm_task_state_by_id':'GET',
                     'delete_vm_metadata_by_id':'DELETE',
                  }
               )
        resources.append(res)
        return resources