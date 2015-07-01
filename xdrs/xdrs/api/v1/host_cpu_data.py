import webob
from webob import exc

from xdrs.api.v1.admin_detection import authorize
from xdrs.api.views import host_cpu_data as host_cpu_data_view
from xdrs.api.openstack import wsgi
from xdrs import hosts
from xdrs import exception
from xdrs.openstack.common.gettextutils import _

class Controller(wsgi.Controller):
    _view_builder_class = host_cpu_data_view.ViewBuilder
    
    def __init__(self, ext_mgr=None, **kwargs):
        super(Controller, self).__init__(**kwargs)
        self.hosts_api = hosts.API()

    def index(self, req):
        context = req.environ['xdrs.context']
        authorize(context, 'get_host_cpu_data')
        
        hosts_cpu_data = self._get_host_cpu_data(req)
        
        return self._view_builder.index(req, hosts_cpu_data)

    def detail(self, req):
        context = req.environ['xdrs.context']
        authorize(context, 'get_host_cpu_data')
        
        hosts_cpu_data = self._get_host_cpu_data(req)
        
        return self._view_builder.detail(req, hosts_cpu_data)

    def show(self, req, id):
        context = req.environ['xdrs.context']
        authorize(context, 'show_host_cpu_data')
        
        try:
            host_cpu_data = self.hosts_api.get_host_cpu_data_by_id(context, id)
        except exception.HostCpuDataNotFound:
            msg = _('host cpu data not found')
            raise webob.exc.HTTPBadRequest(explanation=msg)

        return self._view_builder.show(req, host_cpu_data)

    def _get_host_cpu_data(self, req):
        context = req.environ['xdrs.context']
        
        try:
            host_cpu_data = self.hosts_api.get_all_host_cpu_data(context)
        except exception.HostCpuDataNotFound:
            msg = _('host cpu data not found')
            raise webob.exc.HTTPBadRequest(explanation=msg)

        return host_cpu_data
    
    def create(self, req, body):
        raise exc.HTTPNotImplemented()
    
    def update(self, req, id, body):
        raise exc.HTTPNotImplemented()
    
    def delete(self, req, id, body):
        raise exc.HTTPNotImplemented()


def create_resource():
    return wsgi.Resource(Controller())
