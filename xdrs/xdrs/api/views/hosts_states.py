from xdrs.api.openstack import common

class ViewBuilder(common.ViewBuilder):

    _collection_name = "hosts_states"

    def basic(self, request, host_states):
        return {
            "host_states": {
                "id": host_states["id"],
                "host_task_state": host_states["host_task_state"],
                "host_load_state": host_states["host_load_state"],
                "host_running_state": host_states["host_running_state"],
                "links": self._get_links(request,
                                         host_states["id"],
                                         self._collection_name),
            },
        }

    def show(self, request, host_states):
        host_states = {
            "host_states": {
                "id": host_states["id"],
                "host_name": host_states["host_name"],
                "host_task_state": host_states["host_task_state"],
                "host_load_state": host_states["host_load_state"],
                "host_running_state": host_states["host_running_state"],
                "migration_time": host_states["migration_time"],
                "detection_time": host_states["detection_time"],
                "links": self._get_links(request,
                                         host_states["id"],
                                         self._collection_name),
            },
        }

        return host_states

    def index(self, request, hosts_states):
        """
        Return the 'index' view of hosts_states.
        """
        return self._list_view(self.basic, request, hosts_states)

    def detail(self, request, hosts_states):
        """
        Return the 'detail' view of hosts_states.
        """
        return self._list_view(self.show, request, hosts_states)

    def _list_view(self, func, request, hosts_states):
        """
        Provide a view for a list of hosts_states.
        """
        hosts_states_list = [func(request, host_states)["host_states"] for host_states in hosts_states]
        host_states_links = self._get_collection_links(request,
                                                   host_states,
                                                   self._collection_name,
                                                   "id")
        hosts_states_dict = dict(hosts_states=hosts_states_list)

        if host_states_links:
            hosts_states_dict["host_states_links"] = host_states_links

        return hosts_states_dict