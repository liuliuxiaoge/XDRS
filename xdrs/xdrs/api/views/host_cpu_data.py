from xdrs.api.openstack import common

class ViewBuilder(common.ViewBuilder):

    _collection_name = "hosts_cpu_data"

    def show_basic(self, request, host_cpu_data):
        return {
            "cpu_data": {
                "host_id": host_cpu_data["host_id"],
                "cpu_data": host_cpu_data["cpu_data"],
                "links": self._get_links(request,
                                        host_cpu_data["host_id"],
                                        self._collection_name),
            },
        }

    def show_detail(self, request, host_cpu_data):
        hosts_cpu_data_dict = {
            "cpu_data": {
                "host_id": host_cpu_data["host_id"],
                "host_name": host_cpu_data["host_name"],
                "data_len": host_cpu_data["data_len"],
                "cpu_data": host_cpu_data["cpu_data"],
                "links": self._get_links(request,
                                         host_cpu_data["host_id"],
                                         self._collection_name),
            },
        }

        return hosts_cpu_data_dict

    def index(self, request, hosts_cpu_data):
        """
        Return the 'index' view of hosts cpu data.
        """
        return self._list_view(self.show_basic, request, hosts_cpu_data)

    def detail(self, request, hosts_cpu_data):
        """
        Return the 'detail' view of hosts cpu data.
        """
        return self._list_view(self.show_detail, request, hosts_cpu_data)
    
    def show(self, request, host_cpu_data):
        """
        Return the 'detail' view of hosts cpu data.
        """
        hosts_cpu_data_dict = self.show_detail(request, host_cpu_data)["cpu_data"] 
        return hosts_cpu_data_dict

    def _list_view(self, func, request, hosts_cpu_data):
        """
        Provide a view for a list of hosts cpu data.
        """
        hosts_cpu_data_list = [func(request, host_cpu_data)["cpu_data"] for host_cpu_data in hosts_cpu_data]
        hosts_cpu_data_links = self._get_collection_links(request,
                                                   host_cpu_data,
                                                   self._collection_name,
                                                   "host_id")
        hosts_cpu_data_dict = dict(hosts_cpu_data=hosts_cpu_data_list)

        if hosts_cpu_data_links:
            hosts_cpu_data_dict["host_cpu_data_links"] = hosts_cpu_data_links

        return hosts_cpu_data_dict