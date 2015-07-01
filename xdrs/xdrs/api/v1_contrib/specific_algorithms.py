"""
The algorithms API extension.
algorithms相关API的扩展；
"""

import webob
from webob import exc
import random

from xdrs.api.v1.admin_detection import authorize
from xdrs.api.openstack import extensions
from xdrs.api.openstack import wsgi
from xdrs import hosts
from xdrs import exception
from xdrs.openstack.common.gettextutils import _
from xdrs.openstack.common import log as logging

LOG = logging.getLogger(__name__)


def _translate_underload_algorithms_detail_view(context, algorithm):
    """
    Maps keys for algorithms details view.
    """

    d = _translate_underload_algorithms_summary_view(context, algorithm)

    # No additional data / lookups at the moment

    return d


def _translate_underload_algorithms_summary_view(context, algorithm):
    """
    Maps keys for algorithms summary view.
    """
    
    d = {}

    d['id'] = algorithm['id']
    d['algorithm_name'] = algorithm['algorithm_name']
    d['algorithmid'] = algorithm['algorithmid']
    d['description'] = algorithm['description']
    d['parameters'] = algorithm['parameters']
    LOG.audit(_("algorithm=%s"), algorithm, context=context)

    return d



class UnderloadAlgorithmsController(wsgi.Controller):
    """
    The Underload Algorithms API controller.
    """
    
    def __init__(self, **kwargs):
        super(UnderloadAlgorithmsController, self).__init__(**kwargs)
        self.hosts_api = hosts.API()

    def show(self, req, id):
        """
        Return data about the given algorithm.
        """
        context = req.environ['xdrs.context']
        authorize(context, 'show_algorithms')

        try:
            algorithm = self.hosts_api.get_underload_algorithm_by_id(context, id)
        except exception.NotFound:
            raise exc.HTTPNotFound()
        
        return {'underload_algorithm': _translate_underload_algorithms_detail_view(context, algorithm)}

    def delete(self, req, id):
        """
        Delete a algorithm.
        """
        context = req.environ['xdrs.context']
        authorize(context, 'delete_algorithms')

        try:
            algorithm = self.hosts_api.delete_underload_algorithm_by_id(context, id)
        except exception.NotFound:
            raise exc.HTTPNotFound()
        return webob.Response(status_int=202)
    
    def update(self, req, id, body):
        context = req.environ['xdrs.context']
        authorize(context, 'update_algorithms')
        
        if not self.is_valid_body(body, 'parameters'):
            raise webob.exc.HTTPBadRequest()
        parameters = body['parameters']
        
        try:
            algorithm = self.hosts_api.update_underload_algorithm(context, id, parameters)
        except exception.AlgorithmNotFound as ex:
            raise webob.exc.HTTPNotFound(explanation=ex.format_message())
        
        return {'parameters':parameters}
    

    def index(self, req):
        """
        Returns a summary list of algorithms.
        """
        return self._items(req, entity_maker=_translate_underload_algorithms_summary_view)

    def detail(self, req):
        """
        Returns a detailed list of algorithms.
        """
        return self._items(req, entity_maker=_translate_underload_algorithms_detail_view)

    def _items(self, req, entity_maker):
        """
        Returns a list of algorithms, transformed through entity_maker.
        """
        context = req.environ['xdrs.context']
        authorize(context, 'get_algorithms')
        
        try:
            algorithms = self.hosts_api.get_all_underload_algorithms_sorted_list(context)
        except exception.AlgorithmsNotFound:
            msg = _('underload algorithms not found')
            raise webob.exc.HTTPBadRequest(explanation=msg)
        
        underload_algorithms = [entity_maker(context, algorithm) for algorithm in algorithms]
        return {'underload_algorithms': underload_algorithms}

    def create(self, req, body):
        """
        Creates a new algorithm.
        """
        context = req.environ['xdrs.context']
        authorize(context, 'update_algorithms')
        
        if not self.is_valid_body(body, 'parameters'):
            raise webob.exc.HTTPBadRequest()
        algorithm_parameters = body['parameters']
        
        if not self.is_valid_body(body, 'algorithm_name'):
            raise webob.exc.HTTPBadRequest()
        algorithm_name = body['algorithm_name']
        
        if not self.is_valid_body(body, 'algorithm_description'):
            raise webob.exc.HTTPBadRequest()
        algorithm_description = body['algorithm_description']
        
        algorithm_id = random.randint(0, 0xffffffffffffffff)
        
        algorithm_create_values = {
                                   'algorithm_name': algorithm_name,
                                   'algorithm_id': algorithm_id,
                                   'algorithm_parameters': algorithm_parameters,
                                   'algorithm_description': algorithm_description,
                                   'in_use': False
                                   }
        
        try:
            algorithm = self.hosts_api.create_underload_algorithm(context, algorithm_create_values)
        except exception.AlgorithmNotFound as ex:
            raise webob.exc.HTTPNotFound(explanation=ex.format_message())
        
        return {'algorithm': algorithm}
    
    def get_underload_algorithm_in_used(self, req):
        context = req.environ['xdrs.context']
        authorize(context, 'get_algorithm')

        try:
            algorithm = self.hosts_api.get_underload_algorithm_in_used(context, id)
        except exception.NotFound:
            raise exc.HTTPNotFound()
        
        return {'underload_algorithm': _translate_underload_algorithms_detail_view(context, algorithm)}
   
    
    
def _translate_overload_algorithms_detail_view(context, algorithm):
    """
    Maps keys for algorithms details view.
    """
    d = _translate_overload_algorithms_summary_view(context, algorithm)

    # No additional data / lookups at the moment

    return d


def _translate_overload_algorithms_summary_view(context, algorithm):
    """
    Maps keys for algorithms summary view.
    """
    
    d = {}

    d['id'] = algorithm['id']
    d['algorithm_name'] = algorithm['algorithm_name']
    d['algorithmid'] = algorithm['algorithmid']
    d['description'] = algorithm['description']
    d['parameters'] = algorithm['parameters']
    LOG.audit(_("algorithm=%s"), algorithm, context=context)

    return d



class OverloadAlgorithmsController(wsgi.Controller):
    """
    The Overload Algorithms API controller.
    """
    
    def __init__(self, **kwargs):
        super(OverloadAlgorithmsController, self).__init__(**kwargs)
        self.hosts_api = hosts.API()
    
    def index(self, req):
        """
        Returns a summary list of algorithms.
        """
        return self._items(req, entity_maker=_translate_overload_algorithms_summary_view)

    def detail(self, req):
        """
        Returns a detailed list of algorithms.
        """
        return self._items(req, entity_maker=_translate_overload_algorithms_detail_view)
    
    def show(self, req, id):
        """
        Return data about the given algorithm.
        """
        context = req.environ['xdrs.context']
        authorize(context, 'show_algorithms')

        try:
            algorithm = self.hosts_api.get_overload_algorithm_by_id(context, id)
        except exception.NotFound:
            raise exc.HTTPNotFound()
        
        return {'overload_algorithm': _translate_overload_algorithms_detail_view(context, algorithm)}

    def create(self, req, server_id, body):
        """
        Creates a new algorithm.
        """
        context = req.environ['xdrs.context']
        authorize(context, 'update_algorithms')
        
        if not self.is_valid_body(body, 'parameters'):
            raise webob.exc.HTTPBadRequest()
        algorithm_parameters = body['parameters']
        
        if not self.is_valid_body(body, 'algorithm_name'):
            raise webob.exc.HTTPBadRequest()
        algorithm_name = body['algorithm_name']
        
        if not self.is_valid_body(body, 'algorithm_description'):
            raise webob.exc.HTTPBadRequest()
        algorithm_description = body['algorithm_description']
        
        algorithm_id = random.randint(0, 0xffffffffffffffff)
        
        algorithm_create_values = {
                                   'algorithm_name': algorithm_name,
                                   'algorithm_id': algorithm_id,
                                   'algorithm_parameters': algorithm_parameters,
                                   'algorithm_description': algorithm_description,
                                   'in_use': False
                                   }
        
        try:
            algorithm = self.hosts_api.create_overload_algorithm(context, algorithm_create_values)
        except exception.AlgorithmNotFound as ex:
            raise webob.exc.HTTPNotFound(explanation=ex.format_message())
        
        return {'algorithm': algorithm}


    def update(self, req, id, body):
        context = req.environ['xdrs.context']
        authorize(context, 'update_algorithms')
        
        if not self.is_valid_body(body, 'parameters'):
            raise webob.exc.HTTPBadRequest()
        parameters = body['parameters']
        
        try:
            algorithm = self.hosts_api.update_overload_algorithm(context, id, parameters)
        except exception.AlgorithmNotFound as ex:
            raise webob.exc.HTTPNotFound(explanation=ex.format_message())
        
        return {'parameters':parameters}
    

    def delete(self, req, id):
        """
        Detach a algorithm.
        """
        context = req.environ['xdrs.context']
        authorize(context, 'delete_algorithms')

        try:
            algorithm = self.hosts_api.delete_overload_algorithm_by_id(context, id)
        except exception.NotFound:
            raise exc.HTTPNotFound()
        return webob.Response(status_int=202)

    def _items(self, req, server_id, entity_maker):
        """
        Returns a list of algorithms, transformed through entity_maker.
        """
        context = req.environ['xdrs.context']
        authorize(context, 'get_algorithms')
        
        try:
            algorithms = self.hosts_api.get_all_overload_algorithms_sorted_list(context)
        except exception.AlgorithmsNotFound:
            msg = _('overload algorithms not found')
            raise webob.exc.HTTPBadRequest(explanation=msg)
        
        overload_algorithms = [entity_maker(context, algorithm) for algorithm in algorithms]
        return {'overload_algorithms': overload_algorithms}
    
    def get_overload_algorithm_in_used(self, req):
        context = req.environ['xdrs.context']
        authorize(context, 'get_algorithm')

        try:
            algorithm = self.hosts_api.get_overload_algorithm_in_used(context, id)
        except exception.NotFound:
            raise exc.HTTPNotFound()
        
        return {'overload_algorithm': _translate_overload_algorithms_detail_view(context, algorithm)}


def _translate_filter_scheduler_algorithms_detail_view(context, algorithm):
    """
    Maps keys for algorithms details view.
    """

    d = _translate_filter_scheduler_algorithms_summary_view(context, algorithm)

    # NOTE(gagupta): No additional data / lookups at the moment
    return d


def _translate_filter_scheduler_algorithms_summary_view(context, algorithm):
    """
    Maps keys for algorithms summary view.
    """
    
    d = {}

    d['id'] = algorithm['id']
    d['algorithm_name'] = algorithm['algorithm_name']
    d['algorithmid'] = algorithm['algorithmid']
    d['description'] = algorithm['description']
    d['parameters'] = algorithm['parameters']
    LOG.audit(_("algorithm=%s"), algorithm, context=context)

    return d



class FilterSchedulerAlgorithmsController(wsgi.Controller):
    """
    The Filter Scheduler Algorithms API controller.
    """
    
    def __init__(self, **kwargs):
        super(FilterSchedulerAlgorithmsController, self).__init__(**kwargs)
        self.hosts_api = hosts.API()

    def show(self, req, id):
        """
        Return data about the given algorithm.
        """
        context = req.environ['xdrs.context']
        authorize(context, 'show_algorithms')

        try:
            algorithm = self.hosts_api.get_filter_scheduler_algorithm_by_id(context, id)
        except exception.NotFound:
            raise exc.HTTPNotFound()
        
        return {'filter_scheduler_algorithm': _translate_filter_scheduler_algorithms_detail_view(context, algorithm)}

    def delete(self, req, id):
        """
        Delete a algorithm.
        """
        context = req.environ['xdrs.context']
        authorize(context, 'delete_algorithms')

        try:
            algorithm = self.hosts_api.delete_filter_scheduler_algorithm_by_id(context, id)
        except exception.NotFound:
            raise exc.HTTPNotFound()
        return webob.Response(status_int=202)
    
    def update(self, req, id, body):
        context = req.environ['xdrs.context']
        authorize(context, 'update_algorithms')
        
        if not self.is_valid_body(body, 'parameters'):
            raise webob.exc.HTTPBadRequest()
        parameters = body['parameters']
        
        try:
            algorithm = self.hosts_api.update_filter_scheduler_algorithm(context, id, parameters)
        except exception.AlgorithmNotFound as ex:
            raise webob.exc.HTTPNotFound(explanation=ex.format_message())
        
        return {'parameters':parameters}
    

    def index(self, req):
        """
        Returns a summary list of algorithms.
        """
        return self._items(req, entity_maker=_translate_filter_scheduler_algorithms_summary_view)

    def detail(self, req):
        """
        Returns a detailed list of algorithms.
        """
        return self._items(req, entity_maker=_translate_filter_scheduler_algorithms_detail_view)

    def _items(self, req, entity_maker):
        """
        Returns a list of algorithms, transformed through entity_maker.
        """
        context = req.environ['xdrs.context']
        authorize(context, 'get_algorithms')
        
        try:
            algorithms = self.hosts_api.get_all_filter_scheduler_algorithms_sorted_list(context)
        except exception.AlgorithmsNotFound:
            msg = _('filter scheduler algorithms not found')
            raise webob.exc.HTTPBadRequest(explanation=msg)
        
        filter_scheduler_algorithms = [entity_maker(context, algorithm) for algorithm in algorithms]
        return {'filter_scheduler_algorithms': filter_scheduler_algorithms}

    def create(self, req, body):
        """
        Creates a new algorithm.
        """
        context = req.environ['xdrs.context']
        authorize(context, 'update_algorithms')
        
        if not self.is_valid_body(body, 'parameters'):
            raise webob.exc.HTTPBadRequest()
        algorithm_parameters = body['parameters']
        
        if not self.is_valid_body(body, 'algorithm_name'):
            raise webob.exc.HTTPBadRequest()
        algorithm_name = body['algorithm_name']
        
        if not self.is_valid_body(body, 'algorithm_description'):
            raise webob.exc.HTTPBadRequest()
        algorithm_description = body['algorithm_description']
        
        algorithm_id = random.randint(0, 0xffffffffffffffff)
        
        algorithm_create_values = {
                                   'algorithm_name': algorithm_name,
                                   'algorithm_id': algorithm_id,
                                   'algorithm_parameters': algorithm_parameters,
                                   'algorithm_description': algorithm_description,
                                   'in_use': False
                                   }
        
        try:
            algorithm = self.hosts_api.create_filter_scheduler_algorithm(context, algorithm_create_values)
        except exception.AlgorithmNotFound as ex:
            raise webob.exc.HTTPNotFound(explanation=ex.format_message())
        
        return {'algorithm': algorithm}
    
    def get_filter_scheduler_algorithms_in_used(self, req):
        context = req.environ['xdrs.context']
        authorize(context, 'get_algorithm')

        try:
            algorithms = self.hosts_api.get_filter_scheduler_algorithms_in_used(context)
        except exception.NotFound:
            raise exc.HTTPNotFound()
        
        algorithms_info = [_translate_filter_scheduler_algorithms_detail_view(context, algorithm) for algorithm in algorithms]        
        filter_scheduler_algorithms = [algorithm['algorithm_name'] for algorithm in algorithms_info]
        
        return {'filter_scheduler_algorithms': filter_scheduler_algorithms}
    
    
    
def _translate_host_scheduler_algorithms_detail_view(context, algorithm):
    """
    Maps keys for algorithms details view.
    """

    d = _translate_host_scheduler_algorithms_summary_view(context, algorithm)

    # NOTE(gagupta): No additional data / lookups at the moment
    return d


def _translate_host_scheduler_algorithms_summary_view(context, algorithm):
    """
    Maps keys for algorithms summary view.
    """
    
    d = {}

    d['id'] = algorithm['id']
    d['algorithm_name'] = algorithm['algorithm_name']
    d['algorithmid'] = algorithm['algorithmid']
    d['description'] = algorithm['description']
    d['parameters'] = algorithm['parameters']
    LOG.audit(_("algorithm=%s"), algorithm, context=context)

    return d



class HostSchedulerAlgorithmsController(wsgi.Controller):
    """
    The Host Scheduler Algorithms API controller.
    """
    
    def __init__(self, **kwargs):
        super(HostSchedulerAlgorithmsController, self).__init__(**kwargs)
        self.hosts_api = hosts.API()

    def show(self, req, id):
        """
        Return data about the given algorithm.
        """
        context = req.environ['xdrs.context']
        authorize(context, 'show_algorithms')

        try:
            algorithm = self.hosts_api.get_host_scheduler_algorithm_by_id(context, id)
        except exception.NotFound:
            raise exc.HTTPNotFound()
        
        return {'host_scheduler_algorithm': _translate_host_scheduler_algorithms_detail_view(context, algorithm)}

    def delete(self, req, id):
        """
        Delete a algorithm.
        """
        context = req.environ['xdrs.context']
        authorize(context, 'delete_algorithms')

        try:
            algorithm = self.hosts_api.delete_host_scheduler_algorithm_by_id(context, id)
        except exception.NotFound:
            raise exc.HTTPNotFound()
        return webob.Response(status_int=202)
    
    def update(self, req, id, body):
        context = req.environ['xdrs.context']
        authorize(context, 'update_algorithms')
        
        if not self.is_valid_body(body, 'parameters'):
            raise webob.exc.HTTPBadRequest()
        parameters = body['parameters']
        
        try:
            algorithm = self.hosts_api.update_host_scheduler_algorithm(context, id, parameters)
        except exception.AlgorithmNotFound as ex:
            raise webob.exc.HTTPNotFound(explanation=ex.format_message())
        
        return {'parameters':parameters}
        

    def index(self, req):
        """
        Returns a summary list of algorithms.
        """
        return self._items(req, entity_maker=_translate_host_scheduler_algorithms_summary_view)

    def detail(self, req):
        """
        Returns a detailed list of algorithms.
        """
        return self._items(req, entity_maker=_translate_host_scheduler_algorithms_detail_view)

    def _items(self, req, entity_maker):
        """
        Returns a list of algorithms, transformed through entity_maker.
        """
        context = req.environ['xdrs.context']
        authorize(context, 'get_algorithms')
        
        try:
            algorithms = self.hosts_api.get_all_host_scheduler_algorithms_sorted_list(context)
        except exception.AlgorithmsNotFound:
            msg = _('overload algorithms not found')
            raise webob.exc.HTTPBadRequest(explanation=msg)
        
        host_scheduler_algorithms = [entity_maker(context, algorithm) for algorithm in algorithms]
        return {'host_scheduler_algorithms': host_scheduler_algorithms}

    def create(self, req, body):
        """
        Creates a new algorithm.
        """
        context = req.environ['xdrs.context']
        authorize(context, 'update_algorithms')
        
        if not self.is_valid_body(body, 'parameters'):
            raise webob.exc.HTTPBadRequest()
        algorithm_parameters = body['parameters']
        
        if not self.is_valid_body(body, 'algorithm_name'):
            raise webob.exc.HTTPBadRequest()
        algorithm_name = body['algorithm_name']
        
        if not self.is_valid_body(body, 'algorithm_description'):
            raise webob.exc.HTTPBadRequest()
        algorithm_description = body['algorithm_description']
        
        algorithm_id = random.randint(0, 0xffffffffffffffff)
        
        algorithm_create_values = {
                                   'algorithm_name': algorithm_name,
                                   'algorithm_id': algorithm_id,
                                   'algorithm_parameters': algorithm_parameters,
                                   'algorithm_description': algorithm_description,
                                   'in_use': False
                                   }
        
        try:
            algorithm = self.hosts_api.create_host_scheduler_algorithm(context, algorithm_create_values)
        except exception.AlgorithmNotFound as ex:
            raise webob.exc.HTTPNotFound(explanation=ex.format_message())
        
        return {'algorithm': algorithm}
    
    def get_host_scheduler_algorithm_in_used(self, req):
        context = req.environ['xdrs.context']
        authorize(context, 'get_algorithm')

        try:
            algorithm = self.hosts_api.get_host_scheduler_algorithm_in_used(context)
        except exception.NotFound:
            raise exc.HTTPNotFound()
        
        return {'host_scheduler_algorithm': _translate_host_scheduler_algorithms_detail_view(context, algorithm)}
    
    
def _translate_vm_select_algorithm_detail_view(context, algorithm):
    """
    Maps keys for algorithms details view.
    """

    d = _translate_vm_select_algorithm_summary_view(context, algorithm)

    # NOTE(gagupta): No additional data / lookups at the moment
    return d


def _translate_vm_select_algorithm_summary_view(context, algorithm):
    """
    Maps keys for algorithms summary view.
    """
    
    d = {}

    d['id'] = algorithm['id']
    d['algorithm_name'] = algorithm['algorithm_name']
    d['algorithmid'] = algorithm['algorithmid']
    d['description'] = algorithm['description']
    d['parameters'] = algorithm['parameters']
    LOG.audit(_("algorithm=%s"), algorithm, context=context)

    return d


class VmSelectAlgorithmsController(wsgi.Controller):
    """
    The Vm Select Algorithms API controller.
    """
    
    def __init__(self, **kwargs):
        super(VmSelectAlgorithmsController, self).__init__(**kwargs)
        self.hosts_api = hosts.API()

    def show(self, req, id):
        """
        Return data about the given algorithm.
        """
        context = req.environ['xdrs.context']
        authorize(context, 'show_algorithms')

        try:
            algorithm = self.hosts_api.get_vm_select_algorithm_by_id(context, id)
        except exception.NotFound:
            raise exc.HTTPNotFound()
        
        return {'vm_select_algorithm': _translate_vm_select_algorithm_detail_view(context, algorithm)}

    def delete(self, req, id):
        """
        Delete a algorithm.
        """
        context = req.environ['xdrs.context']
        authorize(context, 'delete_algorithms')

        try:
            algorithm = self.hosts_api.delete_vm_select_algorithm_by_id(context, id)
        except exception.NotFound:
            raise exc.HTTPNotFound()
        return webob.Response(status_int=202)
    
    def update(self, req, id, body):
        context = req.environ['xdrs.context']
        authorize(context, 'update_algorithms')
        
        if not self.is_valid_body(body, 'parameters'):
            raise webob.exc.HTTPBadRequest()
        parameters = body['parameters']
        
        try:
            algorithm = self.hosts_api.update_vm_select_algorithm(context, id, parameters)
        except exception.AlgorithmNotFound as ex:
            raise webob.exc.HTTPNotFound(explanation=ex.format_message())
        
        return {'parameters':parameters}
        

    def index(self, req):
        """
        Returns a summary list of algorithms.
        """
        return self._items(req, entity_maker=_translate_vm_select_algorithm_summary_view)

    def detail(self, req):
        """
        Returns a detailed list of algorithms.
        """
        return self._items(req, entity_maker=_translate_vm_select_algorithm_detail_view)

    def _items(self, req, entity_maker):
        """
        Returns a list of algorithms, transformed through entity_maker.
        """
        context = req.environ['xdrs.context']
        authorize(context, 'get_algorithms')
        
        try:
            algorithms = self.hosts_api.get_all_vm_select_algorithm_sorted_list(context)
        except exception.AlgorithmsNotFound:
            msg = _('overload algorithms not found')
            raise webob.exc.HTTPBadRequest(explanation=msg)
        
        vm_select_algorithms = [entity_maker(context, algorithm) for algorithm in algorithms]
        return {'vm_select_algorithms': vm_select_algorithms}

    def create(self, req, body):
        """
        Creates a new algorithm.
        """
        context = req.environ['xdrs.context']
        authorize(context, 'update_algorithms')
        
        if not self.is_valid_body(body, 'parameters'):
            raise webob.exc.HTTPBadRequest()
        algorithm_parameters = body['parameters']
        
        if not self.is_valid_body(body, 'algorithm_name'):
            raise webob.exc.HTTPBadRequest()
        algorithm_name = body['algorithm_name']
        
        if not self.is_valid_body(body, 'algorithm_description'):
            raise webob.exc.HTTPBadRequest()
        algorithm_description = body['algorithm_description']
        
        algorithm_id = random.randint(0, 0xffffffffffffffff)
        
        algorithm_create_values = {
                                   'algorithm_name': algorithm_name,
                                   'algorithm_id': algorithm_id,
                                   'algorithm_parameters': algorithm_parameters,
                                   'algorithm_description': algorithm_description,
                                   'in_use': False
                                   }
        
        try:
            algorithm = self.hosts_api.create_vm_select_algorithm(context, algorithm_create_values)
        except exception.AlgorithmNotFound as ex:
            raise webob.exc.HTTPNotFound(explanation=ex.format_message())
        
        return {'algorithm': algorithm}
    
    def get_vm_select_algorithm_in_used(self, req):
        context = req.environ['xdrs.context']
        authorize(context, 'get_algorithm')

        try:
            algorithm = self.hosts_api.get_vm_select_algorithm_in_used(context, id)
        except exception.NotFound:
            raise exc.HTTPNotFound()
        
        return {'vm_select_algorithm': _translate_vm_select_algorithm_detail_view(context, algorithm)}


class SpecificAlgorithms(extensions.ExtensionDescriptor):
    """
    specific algorithms support.
    """

    name = "Specific Algorithms"
    alias = "os-specific-algorithms"
    namespace = " "
    updated = "2015-03-25T00:00:00+00:00"

    def get_resources(self):
        resources = []

        """
        注：'update': 'PUT'加上之后，就说明要在命令行中提供更新的相关命令；
        如果不加上就说明虽然在API中实现了更新的功能，但是在命令行中还没有
        提供相应的调用命令；
        """
        res = extensions.ResourceExtension('os-underload-algorithms',
                                        UnderloadAlgorithmsController(),
                                        collection_actions={'get_underload_algorithm_in_used': 'GET'},
                                        )
        resources.append(res)

        res = extensions.ResourceExtension('os-overload-algorithms',
                                        OverloadAlgorithmsController(),
                                        collection_actions={'get_overload_algorithm_in_used': 'GET'})
        resources.append(res)
        
        res = extensions.ResourceExtension('os-filterscheduler-algorithms',
                                        FilterSchedulerAlgorithmsController(),
                                        collection_actions={'get_filter_scheduler_algorithms_in_used': 'GET'})
        resources.append(res)
        
        res = extensions.ResourceExtension('os-hostscheduler-algorithms',
                                        HostSchedulerAlgorithmsController(),
                                        collection_actions={'get_host_scheduler_algorithm_in_used': 'GET'})
        resources.append(res)
        
        res = extensions.ResourceExtension('os-vmselect-algorithms',
                                        VmSelectAlgorithmsController(),
                                        collection_actions={'get_vm_select_algorithm_in_used': 'GET'})
        resources.append(res)

        return resources