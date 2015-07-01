import webob
from webob import exc

from xdrs.api.v1.admin_detection import authorize
from xdrs.api.views import vm_cpu_data as vm_cpu_data_view
from xdrs.api.openstack import wsgi
from xdrs import hosts
from xdrs import exception
from xdrs.openstack.common.gettextutils import _

class Controller(wsgi.Controller):
    _view_builder_class = vm_cpu_data_view.ViewBuilder
    
    def __init__(self, ext_mgr=None, **kwargs):
        super(Controller, self).__init__(**kwargs)
        self.hosts_api = hosts.API()

    def index(self, req):
        context = req.environ['xdrs.context']
        authorize(context, 'get_vm_cpu_data')
        
        vms_cpu_data = self._get_vm_cpu_data(req)
        
        return self._view_builder.index(req, vms_cpu_data)

    def detail(self, req):
        context = req.environ['xdrs.context']
        authorize(context, 'get_vm_cpu_data')
        
        vms_cpu_data = self._get_vm_cpu_data(req)
        
        return self._view_builder.detail(req, vms_cpu_data)   

    def _get_vm_cpu_data(self, req):
        context = req.environ['xdrs.context']
        
        try:
            vms_cpu_data = self.hosts_api.get_all_vms_cpu_data(context)
        except exception.HostCpuDataNotFound:
            msg = _('host cpu data not found')
            raise webob.exc.HTTPBadRequest(explanation=msg)

        return vms_cpu_data
    
    def create(self, req, body):
        raise exc.HTTPNotImplemented()
    
    def update(self, req, id, body):
        raise exc.HTTPNotImplemented()
    
    def show(self, req, id):
        raise exc.HTTPNotImplemented()
    
    def delete(self, req, id, body):
        raise exc.HTTPNotImplemented()


def create_resource():
    return wsgi.Resource(Controller())