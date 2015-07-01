"""
The vm migtation record API extension.
虚拟机实例迁移记录API相关扩展；
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


def _translate_vm_migration_record_detail_view(context, vm_migration_record):
    """
    Maps keys for vm migration record details view.
    """

    d = _translate_vm_migration_record_summary_view(context, vm_migration_record)

    # No additional data / lookups at the moment

    return d


def _translate_vm_migration_record_summary_view(context, vm_migration_record):
    """
    Maps keys for vm migration record summary view.
    """
    
    d = {}

    d['id'] = vm_migration_record['id']
    d['current_host_name'] = vm_migration_record['current_host_name']
    d['current_host_id'] = vm_migration_record['current_host_id']
    d['previous_host_name'] = vm_migration_record['previous_host_name']
    d['previous_host_id'] = vm_migration_record['previous_host_id']
    d['timestamp'] = vm_migration_record['timestamp']
    d['task_state'] = vm_migration_record['task_state']
    LOG.audit(_("vm_migration_record=%s"), vm_migration_record, context=context)

    return d



class VmMigrationRecordController(wsgi.Controller):
    """
    The vm migration record API controller for the OpenStack API.
    """
    
    def __init__(self, **kwargs):
        super(VmMigrationRecordController, self).__init__(**kwargs)
        self.vms_api = vms.API()
        
    def get_specific_vm_migration_task_state(self, req, id):
        context = req.environ['xdrs.context']
        authorize(context, 'get_vm_migration_task_state')
        
        try:
            vm_migration_task_state = self.vms_api.get_specific_vm_migration_task_state(context, id)
        except exception.NotFound:
            raise exc.HTTPNotFound()
        
        return vm_migration_task_state
    
    def get_specific_vm_all_migration_records(self, req, id):
        context = req.environ['xdrs.context']
        authorize(context, 'get_specific_vm_all_migration_records')
        
        try:
            vm_migration_records = self.vms_api.get_specific_vm_all_migration_records(context, id)
        except exception.NotFound:
            raise exc.HTTPNotFound()
        
        vm_migration_records_dict = self._items(req, context, vm_migration_records, entity_maker=_translate_vm_migration_record_detail_view)
        
        return vm_migration_records_dict
        
    def get_specific_host_all_migration_records(self, req, id):
        context = req.environ['xdrs.context']
        authorize(context, 'get_specific_host_all_migration_records')
        
        try:
            vm_migration_records = self.vms_api.get_specific_host_all_migration_records(context, id)
        except exception.NotFound:
            raise exc.HTTPNotFound()
        
        vm_migration_records_dict = self._items(req, context, vm_migration_records, entity_maker=_translate_vm_migration_record_detail_view)
        
        return vm_migration_records_dict
    
    def get_specific_host_all_migration_in_records(self, req, id):
        context = req.environ['xdrs.context']
        authorize(context, 'get_specific_host_all_migration_records')
        
        try:
            vm_migration_records = self.vms_api.get_specific_host_all_migration_in_records(context, id)
        except exception.NotFound:
            raise exc.HTTPNotFound()
        
        vm_migration_records_dict = self._items(req, context, vm_migration_records, entity_maker=_translate_vm_migration_record_detail_view)
        
        return vm_migration_records_dict
    
    def get_specific_host_all_migration_out_records(self, req, id):
        context = req.environ['xdrs.context']
        authorize(context, 'get_specific_host_all_migration_records')
        
        try:
            vm_migration_records = self.vms_api.get_specific_host_all_migration_out_records(context, id)
        except exception.NotFound:
            raise exc.HTTPNotFound()
        
        vm_migration_records_dict = self._items(req, context, vm_migration_records, entity_maker=_translate_vm_migration_record_detail_view)
        
        return vm_migration_records_dict
    
    def _items(self, context, vm_migration_records, entity_maker):
        """
        Returns a list of vms migration records, transformed through entity_maker.
        """
        vm_migration_records = [entity_maker(context, vm_migration_record) for vm_migration_record in vm_migration_records]
        return {'vm_migration_records': vm_migration_records}



class SpecificVmMigrationRecord(extensions.ExtensionDescriptor):
    name = "Specific Vm Migration Record"
    alias = "os-vm-migration-record"
    namespace = " "
    updated = "2015-03-25T00:00:00+00:00"

    def get_resources(self):
        resources = []
        res = extensions.ResourceExtension(
                 'os-vm-migration-record',
                 VmMigrationRecordController(),
                 member_actions={
                     'get_specific_vm_migration_task_state':'GET',
                     'get_specific_vm_all_migration_records':'GET',
                     'get_specific_host_all_migration_records':'GET',
                     'get_specific_host_all_migration_in_records':'GET',
                     'get_specific_host_all_migration_out_records':'GET',
                  }
               )
        resources.append(res)
        return resources