from xdrs.api.openstack import common

class ViewBuilder(common.ViewBuilder):

    _collection_name = "vms_cpu_data"

    def show_basic(self, request, host_cpu_data):
        vm_cpu_data_dict = {
            "cpu_data": {
                "vm_id": host_cpu_data["vm_id"],
                "host_id": host_cpu_data["host_id"],
                "host_name": host_cpu_data["host_name"],
                "data_len": host_cpu_data["data_len"],
                "cpu_data": host_cpu_data["cpu_data"],
                "links": self._get_links(request,
                                         host_cpu_data["host_id"],
                                         self._collection_name),
            },
        }

        return vm_cpu_data_dict

    def show_detail(self, request, host_cpu_data):
        vm_cpu_data_dict = {
            "cpu_data": {
                "vm_id": host_cpu_data["vm_id"],
                "host_id": host_cpu_data["host_id"],
                "host_name": host_cpu_data["host_name"],
                "data_len": host_cpu_data["data_len"],
                "cpu_data": host_cpu_data["cpu_data"],
                "links": self._get_links(request,
                                         host_cpu_data["host_id"],
                                         self._collection_name),
            },
        }

        return vm_cpu_data_dict

    def index(self, request, vms_cpu_data):
        return self._list_view(self.show_basic, request, vms_cpu_data)

    def detail(self, request, vms_cpu_data):
        return self._list_view(self.show_detail, request, vms_cpu_data)

    def _list_view(self, func, request, vms_cpu_data):
        vms_cpu_data_list = [func(request, vm_cpu_data)["cpu_data"] for vm_cpu_data in vms_cpu_data]
        vms_cpu_data_links = self._get_collection_links(request,
                                                   vm_cpu_data,
                                                   self._collection_name,
                                                   "host_id")
        vms_cpu_data_dict = dict(vms_cpu_data=vms_cpu_data_list)

        if vms_cpu_data_links:
            vms_cpu_data_dict["host_cpu_data_links"] = vms_cpu_data_links

        return vms_cpu_data_dict