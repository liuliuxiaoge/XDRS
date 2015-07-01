import webob
from webob import exc

from xdrs.api.v1.admin_detection import authorize
from xdrs.api.views import vm_metadata as vm_metadata_view
from xdrs.api.openstack import wsgi
from xdrs import vms
from xdrs import exception
from xdrs.openstack.common.gettextutils import _

class Controller(wsgi.Controller):
    _view_builder_class = vm_metadata_view.ViewBuilder
    
    def __init__(self, ext_mgr=None, **kwargs):
        super(Controller, self).__init__(**kwargs)
        self.vms_api = vms.API()

    def index(self, req):
        context = req.environ['xdrs.context']
        authorize(context, 'get_vm_metadata')
        
        vms_metadata = self._get_vm_metadata(req)
        
        return self._view_builder.index(req, vms_metadata)

    def detail(self, req):
        context = req.environ['xdrs.context']
        authorize(context, 'get_vm_metadata')
        
        vms_metadata = self._get_vm_metadata(req)
        
        return self._view_builder.detail(req, vms_metadata)   

    def _get_vm_metadata(self, req):
        context = req.environ['xdrs.context']
        
        try:
            vms_metadata = self.vms_api.get_all_vms_metadata(context)
        except exception.VmMetadataNotFound:
            msg = _('vm metadata not found')
            raise webob.exc.HTTPBadRequest(explanation=msg)

        return vms_metadata
    
    def show(self, req, id):
        context = req.environ['xdrs.context']
        authorize(context, 'show_vm_metadata')
        
        try:
            vm_metadata = self.vms_api.get_vm_metadata_by_id(context, id)
        except exception.VmMetadataNotFound:
            msg = _('vm metadata not found')
            raise webob.exc.HTTPBadRequest(explanation=msg)

        return self._view_builder.show(req, vm_metadata)
    
    def delete(self, req, id, body):
        raise exc.HTTPNotImplemented()
    
    def create(self, req, body):
        raise exc.HTTPNotImplemented()  
    
    def update(self, req, id, body):
        raise exc.HTTPNotImplemented()


def create_resource():
    return wsgi.Resource(Controller())