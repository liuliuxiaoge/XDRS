from xdrs.api.openstack import common

class ViewBuilder(common.ViewBuilder):

    _collection_name = "vms_migration_records"

    def show_basic(self, request, vm_migration_record):
        return {
            "vm_migration_record": {
                "id": vm_migration_record["id"],
                "current_host_name": vm_migration_record["current_host_name"],
                "current_host_id": vm_migration_record["current_host_id"],
                "previous_host_name": vm_migration_record["previous_host_name"],
                "previous_host_id": vm_migration_record["previous_host_id"],
                "timestamp": vm_migration_record["timestamp"],
                "task_state": vm_migration_record["task_state"],
            },
        }

    def show_detail(self, request, vm_migration_record):
        vm_migration_record_dict = {
            "vm_migration_record": {
                "id": vm_migration_record["id"],
                "current_host_name": vm_migration_record["current_host_name"],
                "current_host_id": vm_migration_record["current_host_id"],
                "previous_host_name": vm_migration_record["previous_host_name"],
                "previous_host_id": vm_migration_record["previous_host_id"],
                "timestamp": vm_migration_record["timestamp"],
                "task_state": vm_migration_record["task_state"],
            },
        }

        return vm_migration_record_dict

    def index(self, request, vms_migration_records):
        return self._list_view(self.show_basic, request, vms_migration_records)

    def detail(self, request, vms_migration_records):
        return self._list_view(self.show_detail, request, vms_migration_records)
    
    def show(self, request, vm_migration_record):
        vm_migration_record_dict = self.show_detail(request, vm_migration_record)["vm_migration_record"] 
        
        return vm_migration_record_dict

    def _list_view(self, func, request, vms_migration_records):
        vms_migration_records_list = [func(request, vm_migration_record)["cpu_data"] for vm_migration_record in vms_migration_records]
        vms_migration_records_dict = dict(vms_migration_records=vms_migration_records_list)

        return vms_migration_records_dict