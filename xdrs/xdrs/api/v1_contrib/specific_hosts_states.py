"""
The hosts states API extension.
主机状态API相关扩展；
"""

import webob
from webob import exc

from xdrs.api.v1.admin_detection import authorize
from xdrs.api.openstack import extensions
from xdrs.api.openstack import wsgi
from xdrs import hosts
from xdrs import exception
from xdrs import states
from xdrs.openstack.common.gettextutils import _
from xdrs.openstack.common import log as logging

LOG = logging.getLogger(__name__)


def _translate_host_task_states_detail_view(context, host_task_states):
    """
    Maps keys for host task states details view.
    """

    d = _translate_host_task_states_summary_view(context, host_task_states)

    # No additional data / lookups at the moment

    return d


def _translate_host_task_states_summary_view(context, host_task_states):
    """
    Maps keys for host task states summary view.
    """
    
    d = {}

    d['id'] = host_task_states['id']
    d['host_name'] = host_task_states['host_name']
    d['host_task_state'] = host_task_states['host_task_state']
    d['migration_time'] = host_task_states['migration_time']
    d['detection_time'] = host_task_states['detection_time']
    LOG.audit(_("host_task_states=%s"), host_task_states, context=context)

    return d



class HostTaskStateController(wsgi.Controller):
    """
    The host task states API controller for the OpenStack API.
    """
    
    def __init__(self, **kwargs):
        super(HostTaskStateController, self).__init__(**kwargs)
        self.hosts_api = hosts.API()

    def show(self, req, id):
        """
        Return data about the given host task states.
        """
        context = req.environ['xdrs.context']
        authorize(context, 'show_host_task_states')

        try:
            host_task_states = self.hosts_api.get_host_task_states_by_id(context, id)
        except exception.NotFound:
            raise exc.HTTPNotFound()
        
        return {'host_task_states': _translate_host_task_states_detail_view(context, host_task_states)}

    def delete(self, req, id):
        """
        Delete a host task states.
        """
        context = req.environ['xdrs.context']
        authorize(context, 'delete_host_task_states')

        try:
            host_task_states = self.hosts_api.delete_host_task_states_by_id(context, id)
        except exception.NotFound:
            raise exc.HTTPNotFound()
        return webob.Response(status_int=202)
    
    def update(self, req, id, body):
        context = req.environ['xdrs.context']
        authorize(context, 'update_host_task_states')
        
        if not self.is_valid_body(body, 'parameters'):
            raise webob.exc.HTTPBadRequest()
        parameters = body['parameters']
        value = parameters['host_task_state']
        if value not in [states.DETECTING, 
                         states.COLLECTING, 
                         states.MIGRATING_OUT, 
                         states.MIGRATING_IN,
                         states.DO_NOTING]:
            msg = _('host task states info is error!')
            raise webob.exc.HTTPBadRequest(explanation=msg)
        
        update_value = {'host_task_state':value}
        try:
            host_task_states = self.hosts_api.update_host_task_states(context, id, update_value)
        except exception.HostTaskStateNotFound as ex:
            raise webob.exc.HTTPNotFound(explanation=ex.format_message())
        
        return {'host_task_states':host_task_states}
    

    def index(self, req):
        """
        Returns a summary list of hosts task states.
        """
        return self._items(req, entity_maker=_translate_host_task_states_summary_view)

    def detail(self, req):
        """
        Returns a detailed list of hosts task states.
        """
        return self._items(req, entity_maker=_translate_host_task_states_detail_view)

    def _items(self, req, entity_maker):
        """
        Returns a list of hosts task states, transformed through entity_maker.
        """
        context = req.environ['xdrs.context']
        authorize(context, 'get_hosts_task_states')
        
        try:
            hosts_task_states = self.hosts_api.get_all_hosts_task_states_sorted_list(context)
        except exception.AlgorithmsNotFound:
            msg = _('host running states not found')
            raise webob.exc.HTTPBadRequest(explanation=msg)
        
        hosts_task_states = [entity_maker(context, host_task_states) for host_task_states in hosts_task_states]
        return {'hosts_task_states': hosts_task_states}

    def create(self, req, body):
        """
        Creates a new host task states.
        """
        raise exc.HTTPNotImplemented()

   
    
    
def _translate_host_running_states_detail_view(context, host_running_states):
    """
    Maps keys for host running states details view.
    """
    d = _translate_host_running_states_summary_view(context, host_running_states)

    # No additional data / lookups at the moment

    return d


def _translate_host_running_states_summary_view(context, host_running_states):
    """
    Maps keys for host running states summary view.
    """
    d = {}

    d['id'] = host_running_states['id']
    d['host_name'] = host_running_states['host_name']
    d['host_running_state'] = host_running_states['host_running_state']
    LOG.audit(_("host_running_states=%s"), host_running_states, context=context)

    return d


class HostRunningStateController(wsgi.Controller):
    """
    The host running states API controller for the OpenStack API.
    """
    def __init__(self, **kwargs):
        super(HostRunningStateController, self).__init__(**kwargs)
        self.hosts_api = hosts.API()
    
    def index(self, req):
        """
        Returns a summary list of hosts running states.
        """
        return self._items(req, entity_maker=_translate_host_running_states_summary_view)

    def detail(self, req):
        """
        Returns a detailed list of hosts running states.
        """
        return self._items(req, entity_maker=_translate_host_running_states_detail_view)

    def show(self, req, id):
        """
        Return data about the given host running states attachment.
        """
        context = req.environ['xdrs.context']
        authorize(context, 'show_host_running_states')

        try:
            host_running_states = self.hosts_api.get_host_running_states_by_id(context, id)
        except exception.NotFound:
            raise exc.HTTPNotFound()
        
        return {'host_running_states': _translate_host_running_states_detail_view(context, host_running_states)}       


    def create(self, req, server_id, body):
        """
        Creates a new host running states.
        """
        raise exc.HTTPNotImplemented()


    def update(self, req, id, body):
        context = req.environ['xdrs.context']
        authorize(context, 'update_host_running_states')
        
        if not self.is_valid_body(body, 'parameters'):
            raise webob.exc.HTTPBadRequest()
        parameters = body['parameters']
        
        value = parameters['host_running_state']
        if value not in [states.NORMAL_POWER, 
                         states.LOW_POWER]:
            msg = _('host running states info is error!')
            raise webob.exc.HTTPBadRequest(explanation=msg)
        
        update_value = {'host_running_state':value}
        
        try:
            host_running_states = self.hosts_api.update_host_running_states(context, id, update_value)
        except exception.HostRunningStateNotFound as ex:
            raise webob.exc.HTTPNotFound(explanation=ex.format_message())
        
        return {'host_running_states':host_running_states}


    def delete(self, req, id):
        """
        Detach a host running states.
        """
        context = req.environ['xdrs.context']
        authorize(context, 'delete_host_running_states')

        try:
            host_running_states = self.hosts_api.delete_host_running_states_by_id(context, id)
        except exception.NotFound:
            raise exc.HTTPNotFound()
        return webob.Response(status_int=202)
    

    def _items(self, req, server_id, entity_maker):
        """
        Returns a list of hosts running states, transformed through entity_maker.
        """
        context = req.environ['xdrs.context']
        authorize(context, 'get_hosts_running_states')
        
        try:
            hosts_running_states = self.hosts_api.get_all_hosts_running_states_sorted_list(context)
        except exception.HostRunningStateNotFound:
            msg = _('hosts running states not found')
            raise webob.exc.HTTPBadRequest(explanation=msg)
        
        hosts_running_states = [entity_maker(context, host_running_states) for host_running_states in hosts_running_states]
        return {'hosts_running_states': hosts_running_states}



def _translate_host_load_states_detail_view(context, host_load_states):
    """
    Maps keys for host load states details view.
    """
    d = _translate_host_load_states_summary_view(context, host_load_states)

    # No additional data / lookups at the moment

    return d


def _translate_host_load_states_summary_view(context, host_load_states):
    """
    Maps keys for host load states summary view.
    """
    d = {}

    d['id'] = host_load_states['id']
    d['host_name'] = host_load_states['host_name']
    d['host_load_state'] = host_load_states['host_load_state']
    LOG.audit(_("host_load_states=%s"), host_load_states, context=context)

    return d




class HostLoadStateController(wsgi.Controller):
    """
    The host load states API controller for the OpenStack API.
    """
    def __init__(self, **kwargs):
        super(HostLoadStateController, self).__init__(**kwargs)
        self.hosts_api = hosts.API()

    def index(self, req):
        """
        Returns a summary list of hosts load states.
        """
        return self._items(req, entity_maker=_translate_host_load_states_summary_view)

    def detail(self, req):
        """
        Returns a detailed list of hosts load states.
        """
        return self._items(req, entity_maker=_translate_host_load_states_detail_view)

    def show(self, req, id):
        """
        Return data about the given host load states attachment.
        """
        context = req.environ['xdrs.context']
        authorize(context, 'show_host_load_states')

        try:
            host_load_states = self.hosts_api.get_host_load_states_by_id(context, id)
        except exception.NotFound:
            raise exc.HTTPNotFound()
        
        return {'host_load_states': _translate_host_load_states_detail_view(context, host_load_states)}       


    def create(self, req, server_id, body):
        """
        Creates a new host load states.
        """
        raise exc.HTTPNotImplemented()


    def update(self, req, id, body):
        context = req.environ['xdrs.context']
        authorize(context, 'update_host_load_states')
        
        if not self.is_valid_body(body, 'parameters'):
            raise webob.exc.HTTPBadRequest()
        parameters = body['parameters']
        
        value = parameters['host_load_state']
        if value not in [states.NORMALLOAD, 
                         states.OVERLOAD,
                         states.UNDERLOAD]:
            msg = _('host load states info is error!')
            raise webob.exc.HTTPBadRequest(explanation=msg)
        
        update_value = {'host_load_state':value}
        
        try:
            host_load_states = self.hosts_api.update_host_load_states(context, id, update_value)
        except exception.HostLoadStateNotFound as ex:
            raise webob.exc.HTTPNotFound(explanation=ex.format_message())
        
        return {'host_load_states':host_load_states}


    def delete(self, req, id):
        """
        Detach a host load states.
        """
        context = req.environ['xdrs.context']
        authorize(context, 'delete_host_load_states')

        try:
            host_load_states = self.hosts_api.delete_host_load_states_by_id(context, id)
        except exception.NotFound:
            raise exc.HTTPNotFound()
        return webob.Response(status_int=202)
    

    def _items(self, req, server_id, entity_maker):
        """
        Returns a list of hosts load states, transformed through entity_maker.
        """
        context = req.environ['xdrs.context']
        authorize(context, 'get_hosts_load_states')
        
        try:
            hosts_load_states = self.hosts_api.get_all_hosts_load_states_sorted_list(context)
        except exception.HostLoadStateNotFound:
            msg = _('hosts load states not found')
            raise webob.exc.HTTPBadRequest(explanation=msg)
        
        hosts_load_states = [entity_maker(context, host_load_states) for host_load_states in hosts_load_states]
        return {'hosts_load_states': hosts_load_states}


class SpecificHostsStates(extensions.ExtensionDescriptor):
    """
    specific hosts states support.
    """

    name = "Specific Hosts States"
    alias = "os-specific-hosts-states"
    namespace = " "
    updated = "2015-03-25T00:00:00+00:00"

    def get_resources(self):
        resources = []

        """
        注：'update': 'PUT'加上之后，就说明要在命令行中提供更新的相关命令；
        如果不加上就说明虽然在API中实现了更新的功能，但是在命令行中还没有
        提供相应的调用命令；
        """
        res = extensions.ResourceExtension('os-host-task-state',
                                        HostTaskStateController(),
                                        collection_actions={'detail': 'GET',
                                                            'update': 'PUT'},
                                        )
        resources.append(res)

        res = extensions.ResourceExtension('os-host-running-state',
                                        HostRunningStateController(),
                                        collection_actions={'detail': 'GET'})
        resources.append(res)
        
        res = extensions.ResourceExtension('os-host-load-state',
                                        HostLoadStateController(),
                                        collection_actions={'detail': 'GET'})
        resources.append(res)
        
        return resources