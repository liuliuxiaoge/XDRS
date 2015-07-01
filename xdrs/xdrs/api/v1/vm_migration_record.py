import webob
from webob import exc

from xdrs.api.v1.admin_detection import authorize
from xdrs.api.views import vm_migration_record as vm_migration_record_view
from xdrs.api.openstack import wsgi
from xdrs import vms
from xdrs import exception
from xdrs.openstack.common.gettextutils import _

class Controller(wsgi.Controller):
    _view_builder_class = vm_migration_record_view.ViewBuilder
    
    def __init__(self, ext_mgr=None, **kwargs):
        super(Controller, self).__init__(**kwargs)
        self.vms_api = vms.API()

    def index(self, req):
        context = req.environ['xdrs.context']
        authorize(context, 'get_vms_migration_records')
        
        vms_migration_records = self._get_vms_migration_records(req)
        
        return self._view_builder.index(req, vms_migration_records)

    def detail(self, req):
        context = req.environ['xdrs.context']
        authorize(context, 'get_vms_migration_records')
        
        vms_migration_records = self._get_vms_migration_records(req)
        
        return self._view_builder.detail(req, vms_migration_records)

    def show(self, req, id):
        context = req.environ['xdrs.context']
        authorize(context, 'show_vm_migration_record')
        
        try:
            vm_migration_record = self.vms_api.get_vm_migration_record_by_id(context, id)
        except exception.VmMigrationRecordNotFound:
            msg = _('vm migration record not found')
            raise webob.exc.HTTPBadRequest(explanation=msg)

        return self._view_builder.show(req, vm_migration_record)

    def _get_vms_migration_records(self, req):
        context = req.environ['xdrs.context']
        
        try:
            vms_migration_records = self.vms_api.get_all_vms_migration_records(context)
        except exception.VmMigrationRecordNotFound:
            msg = _('vm migration record not found')
            raise webob.exc.HTTPBadRequest(explanation=msg)

        return vms_migration_records
    
    def create(self, req, body):
        context = req.environ['xdrs.context']
        authorize(context, 'create_vm_migration_record')
        
        try:
            vm_migration_record = body['vm_migration_record']
        except (KeyError, TypeError):
            msg = _("Malformed request body")
            raise exc.HTTPBadRequest(explanation=msg)

        new_vm_migration_record = self.vms_api.create_vm_migration_record(
                                                      context,
                                                      vm_migration_record)

        return {'vm_migration_record': new_vm_migration_record}
    
    def update(self, req, id, body):
        raise exc.HTTPNotImplemented()
    
    def delete(self, req, id):
        context = req.environ['xdrs.context']
        authorize(context, 'delete_vm_migration_record')
        
        try:
            vm_migration_record = self.vms_api.delete_vm_migration_record_by_id(context, id)
        except exception.VmMigrationRecordNotFound:
            msg = _('vm migration record not found')
            raise webob.exc.HTTPBadRequest(explanation=msg)

def create_resource():
    return wsgi.Resource(Controller())