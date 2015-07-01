from xdrs.api.openstack import common

class ViewBuilder(common.ViewBuilder):

    _collection_name = "algorithms"

    def basic(self, request, algorithms):
        return {
            "algorithms": {
                "id": algorithms["algorithmid"],
                "name": algorithms["algorithm_name"],
                "links": self._get_links(request,
                                         algorithms["algorithmid"],
                                         self._collection_name),
            },
        }

    def show(self, request, algorithms):
        algorithm_dict = {
            "algorithms": {
                "id": algorithms["algorithmid"],
                "name": algorithms["algorithm_name"],
                "description": algorithms["description"],
                "links": self._get_links(request,
                                         algorithms["algorithmid"],
                                         self._collection_name),
            },
        }

        return algorithm_dict

    def index(self, request, algorithms):
        """Return the 'index' view of algorithms."""
        return self._list_view(self.basic, request, algorithms)

    def detail(self, request, algorithms):
        """Return the 'detail' view of algorithms."""
        return self._list_view(self.show, request, algorithms)

    def _list_view(self, func, request, algorithms):
        """Provide a view for a list of algorithms."""
        algorithm_list = [func(request, algorithm)["algorithm"] for algorithm in algorithms]
        algorithm_links = self._get_collection_links(request,
                                                   algorithm,
                                                   self._collection_name,
                                                   "algorithmid")
        algorithms_dict = dict(algorithms=algorithm_list)

        if algorithm_links:
            algorithms_dict["algorithms_links"] = algorithm_links

        return algorithms_dict