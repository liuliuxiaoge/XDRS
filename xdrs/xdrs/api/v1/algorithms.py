import webob
from webob import exc

from xdrs.api.v1.admin_detection import authorize
from xdrs.api.views import algorithms as algorithms_view
from xdrs.api.openstack import wsgi
from xdrs import hosts
from xdrs import exception
from xdrs.openstack.common.gettextutils import _

class Controller(wsgi.Controller):
    """
    Algorithms controller for the OpenStack API.
    """
    """
    写一个algorithms_view的实现；
    """
    _view_builder_class = algorithms_view.ViewBuilder
    
    def __init__(self, ext_mgr=None, **kwargs):
        super(Controller, self).__init__(**kwargs)
        self.hosts_api = hosts.API()

    def index(self, req):
        """
        Return all algorithms in brief.
        注：这里只是提供一个实现示例，具体功能的实现还有待探讨；
        """
        context = req.environ['xdrs.context']
        authorize(context, 'get_algorithms')
        
        algorithms = self._get_algorithms(req)
        return self._view_builder.index(req, algorithms)

    def detail(self, req):
        """
        Return all algorithms in detail.
        """
        context = req.environ['xdrs.context']
        authorize(context, 'get_algorithms')
        
        algorithms = self._get_algorithms(req)
        
        return self._view_builder.detail(req, algorithms)

    def show(self, req, id):
        """
        Return data about the given algorithms id.
        """
        raise exc.HTTPNotImplemented()

    def _get_algorithms(self, req):
        """
        Helper function that returns a list of algorithms dicts.
        """
        context = req.environ['xdrs.context']
        
        try:
            algorithm = self.hosts_api.get_all_algorithms_sorted_list(context)
        except exception.AlgorithmsNotFound:
            msg = _('algorithms not found')
            raise webob.exc.HTTPBadRequest(explanation=msg)

        return algorithm


def create_resource():
    return wsgi.Resource(Controller())
