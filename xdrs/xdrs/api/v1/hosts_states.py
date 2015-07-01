import webob
from webob import exc

from xdrs.api.v1.admin_detection import authorize
from xdrs.api.views import hosts_states as hosts_states_view
from xdrs.api.openstack import wsgi
from xdrs import hosts
from xdrs import exception
from xdrs.openstack.common.gettextutils import _

class Controller(wsgi.Controller):
    """
    Host state controller for the OpenStack API.
    """
    """
    写一个hosts_states_view的实现；
    """
    _view_builder_class = hosts_states_view.ViewBuilder
    
    def __init__(self, ext_mgr=None, **kwargs):
        super(Controller, self).__init__(**kwargs)
        self.hosts_api = hosts.API()

    def index(self, req):
        """
        Return all hosts states in brief.
        """
        context = req.environ['xdrs.context']
        authorize(context, 'get_hosts_states')
        
        hosts_states = self._get_hosts_states(req)
        return self._view_builder.index(req, hosts_states)

    def detail(self, req):
        """
        Return all hosts states in detail.
        """
        context = req.environ['xdrs.context']
        authorize(context, 'get_hosts_states')
        
        hosts_states = self._get_hosts_states(req)
        
        return self._view_builder.detail(req, hosts_states)

    def show(self, req, id):
        """Return data about the given host states."""
        raise exc.HTTPNotImplemented()

    def _get_hosts_states(self, req):
        """
        Helper function that returns a list of host state dicts.
        """
        context = req.environ['xdrs.context']
        
        try:
            hosts_states = self.hosts_api.get_all_hosts_states(context)
        except exception.HostStateNotFound:
            msg = _('hosts states not found')
            raise webob.exc.HTTPBadRequest(explanation=msg)

        return hosts_states


def create_resource():
    return wsgi.Resource(Controller())