from xdrs.api.openstack import common

class ViewBuilder(common.ViewBuilder):

    _collection_name = "vms_metadata"

    def show_basic(self, request, vm_metadata):
        vms_metadata_dict = {
            "vm_metadata": {
                "id": vm_metadata["id"],
                "vm_state": vm_metadata["vm_state"],
                "host_name": vm_metadata["host_name"],
                "host_id": vm_metadata["host_id"],
            },
        }

        return vms_metadata_dict

    def show_detail(self, request, vm_metadata):
        vms_metadata_dict = {
            "vm_metadata": {
                "id": vm_metadata["id"],
                "vm_state": vm_metadata["vm_state"],
                "host_name": vm_metadata["host_name"],
                "host_id": vm_metadata["host_id"],
            },
        }

        return vms_metadata_dict

    def index(self, request, vms_metadata):
        """
        Return the 'index' view of vms metadata.
        """
        return self._list_view(self.show_basic, request, vms_metadata)

    def detail(self, request, vms_metadata):
        """
        Return the 'detail' view of vms metadata.
        """
        return self._list_view(self.show_detail, request, vms_metadata)
    
    def show(self, request, vm_metadata):
        """
        Return the 'detail' view of vms metadata.
        """
        vm_metadata_dict = self.show_detail(request, vm_metadata)["vm_metadata"] 
        return vm_metadata_dict

    def _list_view(self, func, request, vms_metadata):
        """
        Provide a view for a list of vms metadata.
        """
        vms_metadata_list = [func(request, vm_metadata)["vm_metadata"] for vm_metadata in vms_metadata]
        vms_metadata_links = self._get_collection_links(request,
                                                   vm_metadata,
                                                   self._collection_name,
                                                   "id")
        vms_metadata_dict = dict(vms_metadata=vms_metadata_list)

        if vms_metadata_links:
            vms_metadata_dict["vms_metadata_links"] = vms_metadata_links

        return vms_metadata_dict