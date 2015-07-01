"""
wsgi实现相关，是很重要，回头看的；
"""

import inspect
import math
import time
from xml.dom import minidom

from lxml import etree
import six
import webob

from xdrs.api.openstack import xmlutil
from xdrs import exception
from xdrs.openstack.common import gettextutils
from xdrs.openstack.common.gettextutils import _
from xdrs.openstack.common import jsonutils
from xdrs.openstack.common import log as logging
from xdrs import utils
from xdrs import wsgi


XMLNS_V10 = 'http://docs.rackspacecloud.com/servers/api/v1.0'
XMLNS_V11 = 'http://docs.openstack.org/compute/api/v1.1'
XMLNS_ATOM = 'http://www.w3.org/2005/Atom'

LOG = logging.getLogger(__name__)

SUPPORTED_CONTENT_TYPES = (
    'application/json',
    'application/vnd.openstack.compute+json',
    'application/xml',
    'application/vnd.openstack.compute+xml',
)

_MEDIA_TYPE_MAP = {
    'application/vnd.openstack.compute+json': 'json',
    'application/json': 'json',
    'application/vnd.openstack.compute+xml': 'xml',
    'application/xml': 'xml',
    'application/atom+xml': 'atom',
}

# These are typically automatically created by routes as either defaults
# collection or member methods.
_ROUTES_METHODS = [
    'create',
    'delete',
    'show',
    'update',
]

_METHODS_WITH_BODY = [
    'POST',
    'PUT',
]


class Request(webob.Request):
    """
    Add some OpenStack API-specific logic to the base webob.Request.
    """

    def __init__(self, *args, **kwargs):
        super(Request, self).__init__(*args, **kwargs)
        self._extension_data = {'db_items': {}}

    def cache_db_items(self, key, items, item_key='id'):
        """
        Allow API methods to store objects from a DB query to be
        used by API extensions within the same API request.

        An instance of this class only lives for the lifetime of a
        single API request, so there's no need to implement full
        cache management.
        """
        db_items = self._extension_data['db_items'].setdefault(key, {})
        for item in items:
            db_items[item[item_key]] = item

    def get_db_items(self, key):
        """
        Allow an API extension to get previously stored objects within
        the same API request.

        Note that the object data will be slightly stale.
        """
        return self._extension_data['db_items'][key]

    def get_db_item(self, key, item_key):
        """
        Allow an API extension to get a previously stored object
        within the same API request.

        Note that the object data will be slightly stale.
        """
        return self.get_db_items(key).get(item_key)

    def cache_db_instances(self, instances):
        self.cache_db_items('instances', instances, 'uuid')

    def cache_db_instance(self, instance):
        self.cache_db_items('instances', [instance], 'uuid')

    def get_db_instances(self):
        return self.get_db_items('instances')

    def get_db_instance(self, instance_uuid):
        return self.get_db_item('instances', instance_uuid)

    def cache_db_flavors(self, flavors):
        self.cache_db_items('flavors', flavors, 'flavorid')

    def cache_db_flavor(self, flavor):
        self.cache_db_items('flavors', [flavor], 'flavorid')

    def get_db_flavors(self):
        return self.get_db_items('flavors')

    def get_db_flavor(self, flavorid):
        return self.get_db_item('flavors', flavorid)

    def cache_db_compute_nodes(self, compute_nodes):
        self.cache_db_items('compute_nodes', compute_nodes, 'id')

    def cache_db_compute_node(self, compute_node):
        self.cache_db_items('compute_nodes', [compute_node], 'id')

    def get_db_compute_nodes(self):
        return self.get_db_items('compute_nodes')

    def get_db_compute_node(self, id):
        return self.get_db_item('compute_nodes', id)

    def best_match_content_type(self):
        """
        Determine the requested response content-type.
        """
        if 'xdrs.best_content_type' not in self.environ:
            # Calculate the best MIME type
            content_type = None

            # Check URL path suffix
            parts = self.path.rsplit('.', 1)
            if len(parts) > 1:
                possible_type = 'application/' + parts[1]
                if possible_type in SUPPORTED_CONTENT_TYPES:
                    content_type = possible_type

            if not content_type:
                content_type = self.accept.best_match(SUPPORTED_CONTENT_TYPES)

            self.environ['xdrs.best_content_type'] = (content_type or
                                                      'application/json')

        return self.environ['xdrs.best_content_type']

    def get_content_type(self):
        """
        Determine content type of the request body.
        Does not do any body introspection, only checks header
        """
        if "Content-Type" not in self.headers:
            return None

        content_type = self.content_type

        # NOTE(markmc): text/plain is the default for eventlet and
        # other webservers which use mimetools.Message.gettype()
        # whereas twisted defaults to ''.
        if not content_type or content_type == 'text/plain':
            return None

        if content_type not in SUPPORTED_CONTENT_TYPES:
            raise exception.InvalidContentType(content_type=content_type)

        return content_type

    def best_match_language(self):
        """
        Determine the best available language for the request.
        """
        if not self.accept_language:
            return None
        return self.accept_language.best_match(
                gettextutils.get_available_languages('xdrs'))


class ActionDispatcher(object):
    """
    Maps method name to local methods through action name.
    """

    def dispatch(self, *args, **kwargs):
        """
        Find and call local method.
        """
        action = kwargs.pop('action', 'default')
        action_method = getattr(self, str(action), self.default)
        return action_method(*args, **kwargs)

    def default(self, data):
        raise NotImplementedError()


class TextDeserializer(ActionDispatcher):
    """
    Default request body deserialization.
    """

    def deserialize(self, datastring, action='default'):
        return self.dispatch(datastring, action=action)

    def default(self, datastring):
        return {}


class JSONDeserializer(TextDeserializer):

    def _from_json(self, datastring):
        try:
            return jsonutils.loads(datastring)
        except ValueError:
            msg = _("cannot understand JSON")
            raise exception.MalformedRequestBody(reason=msg)

    def default(self, datastring):
        return {'body': self._from_json(datastring)}


class XMLDeserializer(TextDeserializer):

    def __init__(self, metadata=None):
        """:param metadata: information needed to deserialize xml into
           a dictionary.
        """
        super(XMLDeserializer, self).__init__()
        self.metadata = metadata or {}

    def _from_xml(self, datastring):
        plurals = set(self.metadata.get('plurals', {}))
        node = xmlutil.safe_minidom_parse_string(datastring).childNodes[0]
        return {node.nodeName: self._from_xml_node(node, plurals)}

    def _from_xml_node(self, node, listnames):
        """
        Convert a minidom node to a simple Python type.

        :param listnames: list of XML node names whose subnodes should
                          be considered list items.

        """
        if len(node.childNodes) == 1 and node.childNodes[0].nodeType == 3:
            return node.childNodes[0].nodeValue
        elif node.nodeName in listnames:
            return [self._from_xml_node(n, listnames) for n in node.childNodes]
        else:
            result = dict()
            for attr in node.attributes.keys():
                if not attr.startswith("xmlns"):
                    result[attr] = node.attributes[attr].nodeValue
            for child in node.childNodes:
                if child.nodeType != node.TEXT_NODE:
                    result[child.nodeName] = self._from_xml_node(child,
                                                                 listnames)
            return result

    def find_first_child_named_in_namespace(self, parent, namespace, name):
        """
        Search a nodes children for the first child with a given name.
        """
        for node in parent.childNodes:
            if (node.localName == name and
                node.namespaceURI and
                    node.namespaceURI == namespace):
                return node
        return None

    def find_first_child_named(self, parent, name):
        """
        Search a nodes children for the first child with a given name.
        """
        for node in parent.childNodes:
            if node.localName == name:
                return node
        return None

    def find_children_named(self, parent, name):
        """
        Return all of a nodes children who have the given name.
        """
        for node in parent.childNodes:
            if node.localName == name:
                yield node

    def extract_text(self, node):
        """
        Get the text field contained by the given node.
        """
        ret_val = ""
        for child in node.childNodes:
            if child.nodeType == child.TEXT_NODE:
                ret_val += child.nodeValue
        return ret_val

    def extract_elements(self, node):
        """
        Get only Element type childs from node.
        """
        elements = []
        for child in node.childNodes:
            if child.nodeType == child.ELEMENT_NODE:
                elements.append(child)
        return elements

    def find_attribute_or_element(self, parent, name):
        """
        Get an attribute value; fallback to an element if not found.
        """
        if parent.hasAttribute(name):
            return parent.getAttribute(name)

        node = self.find_first_child_named(parent, name)
        if node:
            return self.extract_text(node)

        return None

    def default(self, datastring):
        return {'body': self._from_xml(datastring)}


class MetadataXMLDeserializer(XMLDeserializer):

    def extract_metadata(self, metadata_node):
        """
        Marshal the metadata attribute of a parsed request.
        """
        metadata = {}
        if metadata_node is not None:
            for meta_node in self.find_children_named(metadata_node, "meta"):
                key = meta_node.getAttribute("key")
                metadata[key] = self.extract_text(meta_node)
        return metadata


class DictSerializer(ActionDispatcher):
    """
    Default request body serialization.
    """

    def serialize(self, data, action='default'):
        return self.dispatch(data, action=action)

    def default(self, data):
        return ""


class JSONDictSerializer(DictSerializer):
    """
    Default JSON request body serialization.
    """

    def default(self, data):
        return jsonutils.dumps(data)


class XMLDictSerializer(DictSerializer):
    def __init__(self, metadata=None, xmlns=None):
        """:param metadata: information needed to deserialize xml into
           a dictionary.
           :param xmlns: XML namespace to include with serialized xml
        """
        super(XMLDictSerializer, self).__init__()
        self.metadata = metadata or {}
        self.xmlns = xmlns

    def default(self, data):
        # We expect data to contain a single key which is the XML root.
        root_key = data.keys()[0]
        doc = minidom.Document()
        node = self._to_xml_node(doc, self.metadata, root_key, data[root_key])

        return self.to_xml_string(node)

    def to_xml_string(self, node, has_atom=False):
        self._add_xmlns(node, has_atom)
        return node.toxml('UTF-8')

    #NOTE (ameade): the has_atom should be removed after all of the
    # xml serializers and view builders have been updated to the current
    # spec that required all responses include the xmlns:atom, the has_atom
    # flag is to prevent current tests from breaking
    def _add_xmlns(self, node, has_atom=False):
        if self.xmlns is not None:
            node.setAttribute('xmlns', self.xmlns)
        if has_atom:
            node.setAttribute('xmlns:atom', "http://www.w3.org/2005/Atom")

    def _to_xml_node(self, doc, metadata, nodename, data):
        """
        Recursive method to convert data members to XML nodes.
        """
        result = doc.createElement(nodename)

        # Set the xml namespace if one is specified
        # TODO(justinsb): We could also use prefixes on the keys
        xmlns = metadata.get('xmlns', None)
        if xmlns:
            result.setAttribute('xmlns', xmlns)

        #TODO(bcwaldon): accomplish this without a type-check
        if isinstance(data, list):
            collections = metadata.get('list_collections', {})
            if nodename in collections:
                metadata = collections[nodename]
                for item in data:
                    node = doc.createElement(metadata['item_name'])
                    node.setAttribute(metadata['item_key'], str(item))
                    result.appendChild(node)
                return result
            singular = metadata.get('plurals', {}).get(nodename, None)
            if singular is None:
                if nodename.endswith('s'):
                    singular = nodename[:-1]
                else:
                    singular = 'item'
            for item in data:
                node = self._to_xml_node(doc, metadata, singular, item)
                result.appendChild(node)
        #TODO(bcwaldon): accomplish this without a type-check
        elif isinstance(data, dict):
            collections = metadata.get('dict_collections', {})
            if nodename in collections:
                metadata = collections[nodename]
                for k, v in data.items():
                    node = doc.createElement(metadata['item_name'])
                    node.setAttribute(metadata['item_key'], str(k))
                    text = doc.createTextNode(str(v))
                    node.appendChild(text)
                    result.appendChild(node)
                return result
            attrs = metadata.get('attributes', {}).get(nodename, {})
            for k, v in data.items():
                if k in attrs:
                    result.setAttribute(k, str(v))
                else:
                    if k == "deleted":
                        v = str(bool(v))
                    node = self._to_xml_node(doc, metadata, k, v)
                    result.appendChild(node)
        else:
            # Type is atom
            node = doc.createTextNode(str(data))
            result.appendChild(node)
        return result

    def _create_link_nodes(self, xml_doc, links):
        link_nodes = []
        for link in links:
            link_node = xml_doc.createElement('atom:link')
            link_node.setAttribute('rel', link['rel'])
            link_node.setAttribute('href', link['href'])
            if 'type' in link:
                link_node.setAttribute('type', link['type'])
            link_nodes.append(link_node)
        return link_nodes

    def _to_xml(self, root):
        """Convert the xml object to an xml string."""
        return etree.tostring(root, encoding='UTF-8', xml_declaration=True)


def serializers(**serializers):
    """
    Attaches serializers to a method.

    This decorator associates a dictionary of serializers with a
    method.  Note that the function attributes are directly
    manipulated; the method is not wrapped.
    """

    def decorator(func):
        if not hasattr(func, 'wsgi_serializers'):
            func.wsgi_serializers = {}
        func.wsgi_serializers.update(serializers)
        return func
    return decorator


def deserializers(**deserializers):
    """
    Attaches deserializers to a method.

    This decorator associates a dictionary of deserializers with a
    method.  Note that the function attributes are directly
    manipulated; the method is not wrapped.
    """

    def decorator(func):
        if not hasattr(func, 'wsgi_deserializers'):
            func.wsgi_deserializers = {}
        func.wsgi_deserializers.update(deserializers)
        return func
    return decorator


def response(code):
    """
    Attaches response code to a method.

    This decorator associates a response code with a method.  Note
    that the function attributes are directly manipulated; the method
    is not wrapped.
    """

    def decorator(func):
        func.wsgi_code = code
        return func
    return decorator


class ResponseObject(object):
    """
    Bundles a response object with appropriate serializers.

    Object that app methods may return in order to bind alternate
    serializers with a response object to be serialized.  Its use is
    optional.
    """

    def __init__(self, obj, code=None, headers=None, **serializers):
        """
        Binds serializers with an object.

        Takes keyword arguments akin to the @serializer() decorator
        for specifying serializers.  Serializers specified will be
        given preference over default serializers or method-specific
        serializers on return.
        """

        self.obj = obj
        self.serializers = serializers
        self._default_code = 200
        self._code = code
        self._headers = headers or {}
        self.serializer = None
        self.media_type = None

    def __getitem__(self, key):
        """
        Retrieves a header with the given name.
        """

        return self._headers[key.lower()]

    def __setitem__(self, key, value):
        """
        Sets a header with the given name to the given value.
        """

        self._headers[key.lower()] = value

    def __delitem__(self, key):
        """
        Deletes the header with the given name.
        """

        del self._headers[key.lower()]

    def _bind_method_serializers(self, meth_serializers):
        """
        Binds method serializers with the response object.

        Binds the method serializers with the response object.
        Serializers specified to the constructor will take precedence
        over serializers specified to this method.

        :param meth_serializers: A dictionary with keys mapping to
                                 response types and values containing
                                 serializer objects.
        """

        # We can't use update because that would be the wrong
        # precedence
        for mtype, serializer in meth_serializers.items():
            self.serializers.setdefault(mtype, serializer)

    def get_serializer(self, content_type, default_serializers=None):
        """
        Returns the serializer for the wrapped object.

        Returns the serializer for the wrapped object subject to the
        indicated content type.  If no serializer matching the content
        type is attached, an appropriate serializer drawn from the
        default serializers will be used.  If no appropriate
        serializer is available, raises InvalidContentType.
        """

        default_serializers = default_serializers or {}

        try:
            mtype = _MEDIA_TYPE_MAP.get(content_type, content_type)
            if mtype in self.serializers:
                return mtype, self.serializers[mtype]
            else:
                return mtype, default_serializers[mtype]
        except (KeyError, TypeError):
            raise exception.InvalidContentType(content_type=content_type)

    def preserialize(self, content_type, default_serializers=None):
        """
        Prepares the serializer that will be used to serialize.

        Determines the serializer that will be used and prepares an
        instance of it for later call.  This allows the serializer to
        be accessed by extensions for, e.g., template extension.
        """

        mtype, serializer = self.get_serializer(content_type,
                                                default_serializers)
        self.media_type = mtype
        self.serializer = serializer()

    def attach(self, **kwargs):
        """
        Attach slave templates to serializers.
        """
        if self.media_type in kwargs:
            self.serializer.attach(kwargs[self.media_type])

    def serialize(self, request, content_type, default_serializers=None):
        """
        Serializes the wrapped object.
        Utility method for serializing the wrapped object.  Returns a
        webob.Response object.
        """

        if self.serializer:
            serializer = self.serializer
        else:
            _mtype, _serializer = self.get_serializer(content_type,
                                                      default_serializers)
            serializer = _serializer()

        response = webob.Response()
        response.status_int = self.code
        for hdr, value in self._headers.items():
            response.headers[hdr] = utils.utf8(str(value))
        response.headers['Content-Type'] = utils.utf8(content_type)
        if self.obj is not None:
            response.body = serializer.serialize(self.obj)

        return response

    @property
    def code(self):
        """
        Retrieve the response status.
        """

        return self._code or self._default_code

    @property
    def headers(self):
        """
        Retrieve the headers.
        """

        return self._headers.copy()


def action_peek_json(body):
    """
    Determine action to invoke.
    """

    try:
        decoded = jsonutils.loads(body)
    except ValueError:
        msg = _("cannot understand JSON")
        raise exception.MalformedRequestBody(reason=msg)

    # Make sure there's exactly one key...
    if len(decoded) != 1:
        msg = _("too many body keys")
        raise exception.MalformedRequestBody(reason=msg)

    # Return the action and the decoded body...
    return decoded.keys()[0]


def action_peek_xml(body):
    """
    Determine action to invoke.
    """

    dom = xmlutil.safe_minidom_parse_string(body)
    action_node = dom.childNodes[0]

    return action_node.tagName


class ResourceExceptionHandler(object):
    """
    Context manager to handle Resource exceptions.

    Used when processing exceptions generated by API implementation
    methods (or their extensions).  Converts most exceptions to Fault
    exceptions, with the appropriate logging.
    """

    def __enter__(self):
        return None

    def __exit__(self, ex_type, ex_value, ex_traceback):
        if not ex_value:
            return True

        if isinstance(ex_value, exception.NotAuthorized):
            raise Fault(webob.exc.HTTPForbidden(
                    explanation=ex_value.format_message()))
        elif isinstance(ex_value, exception.Invalid):
            raise Fault(exception.ConvertedException(
                    code=ex_value.code,
                    explanation=ex_value.format_message()))

        # Under python 2.6, TypeError's exception value is actually a string,
        # so test # here via ex_type instead:
        # http://bugs.python.org/issue7853
        elif issubclass(ex_type, TypeError):
            exc_info = (ex_type, ex_value, ex_traceback)
            LOG.error(_('Exception handling resource: %s') % ex_value,
                    exc_info=exc_info)
            raise Fault(webob.exc.HTTPBadRequest())
        elif isinstance(ex_value, Fault):
            LOG.info(_("Fault thrown: %s"), unicode(ex_value))
            raise ex_value
        elif isinstance(ex_value, webob.exc.HTTPException):
            LOG.info(_("HTTP exception thrown: %s"), unicode(ex_value))
            raise Fault(ex_value)

        # We didn't handle the exception
        return False


class Resource(wsgi.Application):
    """
    WSGI app that handles (de)serialization and controller dispatch.

    WSGI app that reads routing information supplied by RoutesMiddleware
    and calls the requested action method upon its controller.  All
    controller action methods must accept a 'req' argument, which is the
    incoming wsgi.Request. If the operation is a PUT or POST, the controller
    method must also accept a 'body' argument (the deserialized request body).
    They may raise a webob.exc exception or return a dict, which will be
    serialized by requested content type.

    Exceptions derived from webob.exc.HTTPException will be automatically
    wrapped in Fault() to provide API friendly error responses.
    """

    def __init__(self, controller, action_peek=None, inherits=None,
                 **deserializers):
        """
        :param controller: object that implement methods created by routes
                              lib
        :param action_peek: dictionary of routines for peeking into an
                               action request body to determine the
                               desired action
        :param inherits: another resource object that this resource should
                            inherit extensions from. Any action extensions that
                            are applied to the parent resource will also apply
                            to this resource.
        """

        self.controller = controller

        default_deserializers = dict(xml=XMLDeserializer,
                                     json=JSONDeserializer)
        default_deserializers.update(deserializers)

        self.default_deserializers = default_deserializers
        self.default_serializers = dict(xml=XMLDictSerializer,
                                        json=JSONDictSerializer)

        self.action_peek = dict(xml=action_peek_xml,
                                json=action_peek_json)
        self.action_peek.update(action_peek or {})

        # Copy over the actions dictionary
        self.wsgi_actions = {}
        
        """
        获取controller指定的wsgi_action装饰器装饰的扩展方法；
        """
        if controller:
            self.register_actions(controller)

        # Save a mapping of extensions
        self.wsgi_extensions = {}
        self.wsgi_action_extensions = {}
        self.inherits = inherits

    def register_actions(self, controller):
        """
        Registers controller actions with this resource.
        获取controller指定的wsgi_action装饰器装饰的扩展方法；
        """
        actions = getattr(controller, 'wsgi_actions', {})
        """
        获取所有wsgi_action装饰器装饰的扩展方法；
        """
        
        for key, method_name in actions.items():
            self.wsgi_actions[key] = getattr(controller, method_name)


    def register_extensions(self, controller):
        """
        Registers controller extensions with this resource.
        获取所有wsgi_extends装饰器装饰的扩展方法；
        """

        extensions = getattr(controller, 'wsgi_extensions', [])
        
        
        for method_name, action_name in extensions:
            # Look up the extending method
            extension = getattr(controller, method_name)
            """
            获取所有wsgi_extends装饰器装饰的扩展方法；
            """
            
            """
            获取所有@wsgi.extends装饰的扩展方法，有action参数的；
            存储在self.wsgi_action_extensions中；
            @wsgi.extends(action='create')
            """
            if action_name:
                # Extending an action...
                if action_name not in self.wsgi_action_extensions:
                    self.wsgi_action_extensions[action_name] = []
                self.wsgi_action_extensions[action_name].append(extension)

            """
            获取所有@wsgi.extends装饰的扩展方法，没有action参数的；
            存储在self.wsgi_extensions中；
            @wsgi.extends
            """
            else:
                # Extending a regular method
                if method_name not in self.wsgi_extensions:
                    self.wsgi_extensions[method_name] = []
                self.wsgi_extensions[method_name].append(extension)


    def get_action_args(self, request_environment):
        """
        Parse dictionary created by routes library.
        """

        # NOTE(Vek): Check for get_action_args() override in the
        # controller
        if hasattr(self.controller, 'get_action_args'):
            return self.controller.get_action_args(request_environment)

        try:
            args = request_environment['wsgiorg.routing_args'][1].copy()
        except (KeyError, IndexError, AttributeError):
            return {}

        try:
            del args['controller']
        except KeyError:
            pass

        try:
            del args['format']
        except KeyError:
            pass

        return args

    def get_body(self, request):
        try:
            content_type = request.get_content_type()
        except exception.InvalidContentType:
            LOG.debug(_("Unrecognized Content-Type provided in request"))
            return None, ''

        return content_type, request.body

    def deserialize(self, meth, content_type, body):
        """
        获取指定的反序列化方法； 
        根据确定的反序列化方法对body进行反序列化的实现；
        """
        """
        获取指定的反序列化方法； 
        """
        meth_deserializers = getattr(meth, 'wsgi_deserializers', {})
        try:
            """
            _MEDIA_TYPE_MAP = {   
            'application/vnd.openstack.volume+json': 'json',   
            'application/json': 'json',   
            'application/vnd.openstack.volume+xml': 'xml',   
            'application/xml': 'xml',   
            'application/atom+xml': 'atom',   
            }   
            content_type = application/json
            mtype = json
            """
            mtype = _MEDIA_TYPE_MAP.get(content_type, content_type)
            
            if mtype in meth_deserializers:
                deserializer = meth_deserializers[mtype]
            else:
                deserializer = self.default_deserializers[mtype]
        except (KeyError, TypeError):
            raise exception.InvalidContentType(content_type=content_type)

        """
        根据确定的反序列化方法对body进行反序列化的实现；
        """
        if (hasattr(deserializer, 'want_controller')
                and deserializer.want_controller):
            return deserializer(self.controller).deserialize(body)
        else:
            return deserializer().deserialize(body)

    def pre_process_extensions(self, extensions, request, action_args):
        # List of callables for post-processing extensions
        post = []

        for ext in extensions:
            if inspect.isgeneratorfunction(ext):
                response = None

                # If it's a generator function, the part before the
                # yield is the preprocessing stage
                try:
                    with ResourceExceptionHandler():
                        gen = ext(req=request, **action_args)
                        response = gen.next()
                except Fault as ex:
                    response = ex

                # We had a response...
                if response:
                    return response, []

                # No response, queue up generator for post-processing
                post.append(gen)
            else:
                # Regular functions only perform post-processing
                post.append(ext)

        # Run post-processing in the reverse order
        """
        扩展方法的执行顺序：
        ======================================================================================
        method SecurityGroupsOutputController.detail
        获取resp_obj中所有虚拟机实例的安全组的相关信息，将其写入resp_obj中；
        ======================================================================================
        method keypairs.Controller.detail
        获取resp_obj中每个虚拟机实例的key_name值，将其写入resp_obj中；
        ======================================================================================
        method hide_server_addresses.Controller.detail
        实现在resp_obj中隐藏虚拟机实例的地址；
        ======================================================================================
        method ExtendedVolumesController.detail
        获取resp_obj中每个虚拟机实例所挂载的所有的卷id值，将其写入resp_obj中；
        ======================================================================================
        method config_drive.Controller.detail
        获取resp_obj中每个虚拟机实例的config_drive值，将其写入resp_obj中；
        ======================================================================================
        method ServerUsageController.detail
        获取resp_obj中每个虚拟机实例的启动和中止的时间等值，将其写入resp_obj中；
        ======================================================================================
        method ExtendedStatusController.detail
        获取resp_obj中每个虚拟机实例的task_state/vm_state/power_state等值，将其写入resp_obj中；
        ======================================================================================
        method ExtendedServerAttributesController.detail
        获取resp_obj中每个虚拟机实例的hypervisor_hostname/instance_name/host等值，将其写入resp_obj中；
        ======================================================================================
        method ExtendedIpsMacController.detail
        获取resp_obj中每个虚拟机实例的所有mac_addr的值，将其写入resp_obj中；
        ======================================================================================
        method ExtendedIpsController.detail
        获取resp_obj中每个虚拟机实例的所有ip_type的值，将其写入resp_obj中；
        ======================================================================================
        method ExtendedAZController.detail
        获取resp_obj中每个虚拟机实例的availability_zone的值，将其写入resp_obj中；
        ======================================================================================
        method ServerDiskConfigController.detail
        获取resp_obj中每个虚拟机实例的diskConfig的值，将其写入resp_obj中；
        ======================================================================================
        """
        return None, reversed(post)
    
    def post_process_extensions(self, extensions, resp_obj, request,
                                action_args):
        for ext in extensions:
            response = None
            if inspect.isgenerator(ext):
                # If it's a generator, run the second half of
                # processing
                try:
                    with ResourceExceptionHandler():
                        response = ext.send(resp_obj)
                except StopIteration:
                    # Normal exit of generator
                    continue
                except Fault as ex:
                    response = ex
            else:
                # Regular functions get post-processing...
                try:
                    with ResourceExceptionHandler():
                        response = ext(req=request, resp_obj=resp_obj,
                                       **action_args)
                except Fault as ex:
                    response = ex

            # We had a response...
            if response:
                return response

        return None

    def _should_have_body(self, request):
        """
        如果method为POST或者PUT的话，req中就会有body部分；
        如果method不是POST和PUT的话，req中就不会有body部分；
        """
        return request.method in _METHODS_WITH_BODY

    
    @webob.dec.wsgify(RequestClass=Request)
    """
    wsgify：这个方法主要实现了对请求信息req和执行请求之后的响应信息进行了一些格式和内容上的处理操作；
    这里有一条比较重要的语句：
    req = self.RequestClass(environ)
    就这里的示例来讲，输出示例为self.RequestClass = <class 'cinder.api.openstack.wsgi.Request'>，
    所实现的功能就是通过现有的请求信息，对类Request进行实例初始化，
    形成后面所要应用到的常见格式的req。
    
    语句resp = self.call_func(req, *args, **self.kwargs)，
    这条语句实现的就是调用上面提到的若干中间件的__call__方法；
    """
    def __call__(self, request):
        """
        WSGI method that controls (de)serialization and method dispatch.
        action执行前的一些预处理操作；
        """
        """
        ======================================================================================
        request = GET /v2/4537aca4a4a4462fa4c59ad5b5581f00/servers/detail HTTP/1.0
        Accept: application/json
        Accept-Encoding: gzip, deflate, compress
        Content-Length: 0
        Content-Type: text/plain
        Host: 172.21.7.40:8774
        User-Agent: python-novaclient
        X-Auth-Project-Id: admin
        X-Auth-Token: MIIT9wYJKoZIhvcNAQcCoIIT6DCCE+QCAQExCTAHBgUrDgMCGjCCEk0GCSqGSIb3DQEHAaCCEj4EghI6eyJhY2Nlc3MiOiB7InRva2VuIjogeyJpc3N1ZWRfYXQiOiAiMjAxNS0wMy0xNlQwMzozNjoyNS43OTc5MjAiLCAiZXhwaXJlcyI6ICIyMDE1LTAzLTE2VDA0OjM2OjI1WiIsICJpZCI6ICJwbGFjZWhvbGRlciIsICJ0ZW5hbnQiOiB7ImRlc2NyaXB0aW9uIjogImFkbWluIHRlbmFudCIsICJlbmFibGVkIjogdHJ1ZSwgImlkIjogIjQ1MzdhY2E0YTRhNDQ2MmZhNGM1OWFkNWI1NTgxZjAwIiwgIm5hbWUiOiAiYWRtaW4ifX0sICJzZXJ2aWNlQ2F0YWxvZyI6IFt7ImVuZHBvaW50cyI6IFt7ImFkbWluVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo4Nzc0L3YyLzQ1MzdhY2E0YTRhNDQ2MmZhNGM1OWFkNWI1NTgxZjAwIiwgInJlZ2lvbiI6ICJSZWdpb25PbmUiLCAiaW50ZXJuYWxVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjg3NzQvdjIvNDUzN2FjYTRhNGE0NDYyZmE0YzU5YWQ1YjU1ODFmMDAiLCAiaWQiOiAiMTZiMTVjYzVmZjUwNGNiODlmNTg2NjRlMjdhNjljNjkiLCAicHVibGljVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo4Nzc0L3YyLzQ1MzdhY2E0YTRhNDQ2MmZhNGM1OWFkNWI1NTgxZjAwIn1dLCAiZW5kcG9pbnRzX2xpbmtzIjogW10sICJ0eXBlIjogImNvbXB1dGUiLCAibmFtZSI6ICJub3ZhIn0sIHsiZW5kcG9pbnRzIjogW3siYWRtaW5VUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjk2OTYvIiwgInJlZ2lvbiI6ICJSZWdpb25PbmUiLCAiaW50ZXJuYWxVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjk2OTYvIiwgImlkIjogIjFiMjkzYTgxNjk2YjRiN2Y4OTZlYWQ0NjIyYTFjMmExIiwgInB1YmxpY1VSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6OTY5Ni8ifV0sICJlbmRwb2ludHNfbGlua3MiOiBbXSwgInR5cGUiOiAibmV0d29yayIsICJuYW1lIjogIm5ldXRyb24ifSwgeyJlbmRwb2ludHMiOiBbeyJhZG1pblVSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODc3Ni92Mi80NTM3YWNhNGE0YTQ0NjJmYTRjNTlhZDViNTU4MWYwMCIsICJyZWdpb24iOiAiUmVnaW9uT25lIiwgImludGVybmFsVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo4Nzc2L3YyLzQ1MzdhY2E0YTRhNDQ2MmZhNGM1OWFkNWI1NTgxZjAwIiwgImlkIjogIjNhNzY3OWNjZTdkZjRhY2ZhMTZiM2NhNTJkZGNmYzgyIiwgInB1YmxpY1VSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODc3Ni92Mi80NTM3YWNhNGE0YTQ0NjJmYTRjNTlhZDViNTU4MWYwMCJ9XSwgImVuZHBvaW50c19saW5rcyI6IFtdLCAidHlwZSI6ICJ2b2x1bWV2MiIsICJuYW1lIjogImNpbmRlcnYyIn0sIHsiZW5kcG9pbnRzIjogW3siYWRtaW5VUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjg3NzQvdjMiLCAicmVnaW9uIjogIlJlZ2lvbk9uZSIsICJpbnRlcm5hbFVSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODc3NC92MyIsICJpZCI6ICIwYmIxZDFiODhhZmU0MGRhOTNiY2IxNTg0Y2ExN2ZiOSIsICJwdWJsaWNVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjg3NzQvdjMifV0sICJlbmRwb2ludHNfbGlua3MiOiBbXSwgInR5cGUiOiAiY29tcHV0ZXYzIiwgIm5hbWUiOiAibm92YXYzIn0sIHsiZW5kcG9pbnRzIjogW3siYWRtaW5VUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjgwODAiLCAicmVnaW9uIjogIlJlZ2lvbk9uZSIsICJpbnRlcm5hbFVSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODA4MCIsICJpZCI6ICIxZTMyZTE3MmU3OWM0YzVhYTZiNWM3ZjhkNzVhZjRmYiIsICJwdWJsaWNVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjgwODAifV0sICJlbmRwb2ludHNfbGlua3MiOiBbXSwgInR5cGUiOiAiczMiLCAibmFtZSI6ICJzd2lmdF9zMyJ9LCB7ImVuZHBvaW50cyI6IFt7ImFkbWluVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo5MjkyIiwgInJlZ2lvbiI6ICJSZWdpb25PbmUiLCAiaW50ZXJuYWxVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjkyOTIiLCAiaWQiOiAiM2QxYzc5MjY1MWEwNDljNWE2MWUzNWJmZWZjNGM4OGIiLCAicHVibGljVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo5MjkyIn1dLCAiZW5kcG9pbnRzX2xpbmtzIjogW10sICJ0eXBlIjogImltYWdlIiwgIm5hbWUiOiAiZ2xhbmNlIn0sIHsiZW5kcG9pbnRzIjogW3siYWRtaW5VUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjg3NzciLCAicmVnaW9uIjogIlJlZ2lvbk9uZSIsICJpbnRlcm5hbFVSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODc3NyIsICJpZCI6ICIzOWE0YzA2NDIzYTg0OTNjOTI4ZGExOGY0YTVjY2MxZiIsICJwdWJsaWNVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjg3NzcifV0sICJlbmRwb2ludHNfbGlua3MiOiBbXSwgInR5cGUiOiAibWV0ZXJpbmciLCAibmFtZSI6ICJjZWlsb21ldGVyIn0sIHsiZW5kcG9pbnRzIjogW3siYWRtaW5VUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjgwMDAvdjEvIiwgInJlZ2lvbiI6ICJSZWdpb25PbmUiLCAiaW50ZXJuYWxVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjgwMDAvdjEvIiwgImlkIjogIjU1NzBiOGY4MTE0OTRlMWI5NTVkYjZlNTAzZGYyYWZkIiwgInB1YmxpY1VSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODAwMC92MS8ifV0sICJlbmRwb2ludHNfbGlua3MiOiBbXSwgInR5cGUiOiAiY2xvdWRmb3JtYXRpb24iLCAibmFtZSI6ICJoZWF0LWNmbiJ9LCB7ImVuZHBvaW50cyI6IFt7ImFkbWluVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo4Nzc2L3YxLzQ1MzdhY2E0YTRhNDQ2MmZhNGM1OWFkNWI1NTgxZjAwIiwgInJlZ2lvbiI6ICJSZWdpb25PbmUiLCAiaW50ZXJuYWxVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjg3NzYvdjEvNDUzN2FjYTRhNGE0NDYyZmE0YzU5YWQ1YjU1ODFmMDAiLCAiaWQiOiAiMGExYzhkYTRmMTU2NDk1YWFkMjEzMGUyYzA2OTE5ODIiLCAicHVibGljVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo4Nzc2L3YxLzQ1MzdhY2E0YTRhNDQ2MmZhNGM1OWFkNWI1NTgxZjAwIn1dLCAiZW5kcG9pbnRzX2xpbmtzIjogW10sICJ0eXBlIjogInZvbHVtZSIsICJuYW1lIjogImNpbmRlciJ9LCB7ImVuZHBvaW50cyI6IFt7ImFkbWluVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo4NzczL3NlcnZpY2VzL0FkbWluIiwgInJlZ2lvbiI6ICJSZWdpb25PbmUiLCAiaW50ZXJuYWxVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjg3NzMvc2VydmljZXMvQ2xvdWQiLCAiaWQiOiAiMDMzZjY3ZTk1MDBjNDljYThmOGIxODkzZTJhN2VkYWYiLCAicHVibGljVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo4NzczL3NlcnZpY2VzL0Nsb3VkIn1dLCAiZW5kcG9pbnRzX2xpbmtzIjogW10sICJ0eXBlIjogImVjMiIsICJuYW1lIjogIm5vdmFfZWMyIn0sIHsiZW5kcG9pbnRzIjogW3siYWRtaW5VUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjgwMDQvdjEvNDUzN2FjYTRhNGE0NDYyZmE0YzU5YWQ1YjU1ODFmMDAiLCAicmVnaW9uIjogIlJlZ2lvbk9uZSIsICJpbnRlcm5hbFVSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODAwNC92MS80NTM3YWNhNGE0YTQ0NjJmYTRjNTlhZDViNTU4MWYwMCIsICJpZCI6ICI0YmViNjQ0MjUzYWU0NzdmOWU5NDk2ZWVkZDEwOTNhNSIsICJwdWJsaWNVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjgwMDQvdjEvNDUzN2FjYTRhNGE0NDYyZmE0YzU5YWQ1YjU1ODFmMDAifV0sICJlbmRwb2ludHNfbGlua3MiOiBbXSwgInR5cGUiOiAib3JjaGVzdHJhdGlvbiIsICJuYW1lIjogImhlYXQifSwgeyJlbmRwb2ludHMiOiBbeyJhZG1pblVSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODA4MC8iLCAicmVnaW9uIjogIlJlZ2lvbk9uZSIsICJpbnRlcm5hbFVSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODA4MC92MS9BVVRIXzQ1MzdhY2E0YTRhNDQ2MmZhNGM1OWFkNWI1NTgxZjAwIiwgImlkIjogIjNhMTA2MzU0MjYxMDQzMjk5YTVkMjQ3ZTVmMjU5NGQyIiwgInB1YmxpY1VSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODA4MC92MS9BVVRIXzQ1MzdhY2E0YTRhNDQ2MmZhNGM1OWFkNWI1NTgxZjAwIn1dLCAiZW5kcG9pbnRzX2xpbmtzIjogW10sICJ0eXBlIjogIm9iamVjdC1zdG9yZSIsICJuYW1lIjogInN3aWZ0In0sIHsiZW5kcG9pbnRzIjogW3siYWRtaW5VUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjM1MzU3L3YyLjAiLCAicmVnaW9uIjogIlJlZ2lvbk9uZSIsICJpbnRlcm5hbFVSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6NTAwMC92Mi4wIiwgImlkIjogIjVjNGVlN2MzMTE4NDQyNGM5NDJhMWM1MjgxODU3MmZiIiwgInB1YmxpY1VSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6NTAwMC92Mi4wIn1dLCAiZW5kcG9pbnRzX2xpbmtzIjogW10sICJ0eXBlIjogImlkZW50aXR5IiwgIm5hbWUiOiAia2V5c3RvbmUifV0sICJ1c2VyIjogeyJ1c2VybmFtZSI6ICJhZG1pbiIsICJyb2xlc19saW5rcyI6IFtdLCAiaWQiOiAiOTFkNzMyYjY1ODMxNDkxZDhiZDk1MmIzMTExZTYyZGQiLCAicm9sZXMiOiBbeyJuYW1lIjogImhlYXRfc3RhY2tfb3duZXIifSwgeyJuYW1lIjogIl9tZW1iZXJfIn0sIHsibmFtZSI6ICJhZG1pbiJ9XSwgIm5hbWUiOiAiYWRtaW4ifSwgIm1ldGFkYXRhIjogeyJpc19hZG1pbiI6IDAsICJyb2xlcyI6IFsiZDlmZGVlODI1NjE3NGJlNWE3MmFjZGZmNDNkM2VkZDMiLCAiOWZlMmZmOWVlNDM4NGIxODk0YTkwODc4ZDNlOTJiYWIiLCAiN2E1ZTg5MmFiYTE5NDI3NWI3ZjQxZWM4Njg2ZDUwOGYiXX19fTGCAYEwggF9AgEBMFwwVzELMAkGA1UEBhMCVVMxDjAMBgNVBAgMBVVuc2V0MQ4wDAYDVQQHDAVVbnNldDEOMAwGA1UECgwFVW5zZXQxGDAWBgNVBAMMD3d3dy5leGFtcGxlLmNvbQIBATAHBgUrDgMCGjANBgkqhkiG9w0BAQEFAASCAQBQf7jWBgs5NTmDg+GrOkg0QwZYl2FIs8QEEq+cUGKHpZw47RuWYTpxth3r7YBWXHuVkj41o3y44r8X+KWqMh0-gRloztQQs5j+OjmnnTevqcU7nMb-mIInEflwr6OfVG0n7bwmb8880637z658op-30jnD-ls129Zwy4jAapXblYsFnPU6i8C-3CCzqdP7kd3F1DZmBVwxntuCFXkNCIiD1d-FZnGgdp1l4ruUfX5JffWAkaP77LfmVz3McsxSXLF4n13dF+B7O29bAz+s+TOvS+QtPjh57kyZoR9fPAIDQNomZYOJd0M9b0XMDNFoi60p47rzeUoZyTkZKsROSI9W
        X-Domain-Id: None
        X-Domain-Name: None
        X-Identity-Status: Confirmed
        X-Project-Domain-Id: default
        X-Project-Domain-Name: Default
        X-Project-Id: 4537aca4a4a4462fa4c59ad5b5581f00
        X-Project-Name: admin
        X-Role: heat_stack_owner,_member_,admin
        X-Roles: heat_stack_owner,_member_,admin
        X-Service-Catalog: [{"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:8774/v2/4537aca4a4a4462fa4c59ad5b5581f00", "region": "RegionOne", "publicURL": "http://172.21.7.40:8774/v2/4537aca4a4a4462fa4c59ad5b5581f00", "internalURL": "http://172.21.7.40:8774/v2/4537aca4a4a4462fa4c59ad5b5581f00", "id": "16b15cc5ff504cb89f58664e27a69c69"}], "type": "compute", "name": "nova"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:9696/", "region": "RegionOne", "publicURL": "http://172.21.7.40:9696/", "internalURL": "http://172.21.7.40:9696/", "id": "1b293a81696b4b7f896ead4622a1c2a1"}], "type": "network", "name": "neutron"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:8776/v2/4537aca4a4a4462fa4c59ad5b5581f00", "region": "RegionOne", "publicURL": "http://172.21.7.40:8776/v2/4537aca4a4a4462fa4c59ad5b5581f00", "internalURL": "http://172.21.7.40:8776/v2/4537aca4a4a4462fa4c59ad5b5581f00", "id": "3a7679cce7df4acfa16b3ca52ddcfc82"}], "type": "volumev2", "name": "cinderv2"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:8774/v3", "region": "RegionOne", "publicURL": "http://172.21.7.40:8774/v3", "internalURL": "http://172.21.7.40:8774/v3", "id": "0bb1d1b88afe40da93bcb1584ca17fb9"}], "type": "computev3", "name": "novav3"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:8080", "region": "RegionOne", "publicURL": "http://172.21.7.40:8080", "internalURL": "http://172.21.7.40:8080", "id": "1e32e172e79c4c5aa6b5c7f8d75af4fb"}], "type": "s3", "name": "swift_s3"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:9292", "region": "RegionOne", "publicURL": "http://172.21.7.40:9292", "internalURL": "http://172.21.7.40:9292", "id": "3d1c792651a049c5a61e35bfefc4c88b"}], "type": "image", "name": "glance"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:8777", "region": "RegionOne", "publicURL": "http://172.21.7.40:8777", "internalURL": "http://172.21.7.40:8777", "id": "39a4c06423a8493c928da18f4a5ccc1f"}], "type": "metering", "name": "ceilometer"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:8000/v1/", "region": "RegionOne", "publicURL": "http://172.21.7.40:8000/v1/", "internalURL": "http://172.21.7.40:8000/v1/", "id": "5570b8f811494e1b955db6e503df2afd"}], "type": "cloudformation", "name": "heat-cfn"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:8776/v1/4537aca4a4a4462fa4c59ad5b5581f00", "region": "RegionOne", "publicURL": "http://172.21.7.40:8776/v1/4537aca4a4a4462fa4c59ad5b5581f00", "internalURL": "http://172.21.7.40:8776/v1/4537aca4a4a4462fa4c59ad5b5581f00", "id": "0a1c8da4f156495aad2130e2c0691982"}], "type": "volume", "name": "cinder"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:8773/services/Admin", "region": "RegionOne", "publicURL": "http://172.21.7.40:8773/services/Cloud", "internalURL": "http://172.21.7.40:8773/services/Cloud", "id": "033f67e9500c49ca8f8b1893e2a7edaf"}], "type": "ec2", "name": "nova_ec2"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:8004/v1/4537aca4a4a4462fa4c59ad5b5581f00", "region": "RegionOne", "publicURL": "http://172.21.7.40:8004/v1/4537aca4a4a4462fa4c59ad5b5581f00", "internalURL": "http://172.21.7.40:8004/v1/4537aca4a4a4462fa4c59ad5b5581f00", "id": "4beb644253ae477f9e9496eedd1093a5"}], "type": "orchestration", "name": "heat"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:8080/", "region": "RegionOne", "publicURL": "http://172.21.7.40:8080/v1/AUTH_4537aca4a4a4462fa4c59ad5b5581f00", "internalURL": "http://172.21.7.40:8080/v1/AUTH_4537aca4a4a4462fa4c59ad5b5581f00", "id": "3a106354261043299a5d247e5f2594d2"}], "type": "object-store", "name": "swift"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:35357/v2.0", "region": "RegionOne", "publicURL": "http://172.21.7.40:5000/v2.0", "internalURL": "http://172.21.7.40:5000/v2.0", "id": "5c4ee7c31184424c942a1c52818572fb"}], "type": "identity", "name": "keystone"}]
        X-Tenant: admin
        X-Tenant-Id: 4537aca4a4a4462fa4c59ad5b5581f00
        X-Tenant-Name: admin
        X-User: admin
        X-User-Domain-Id: default
        X-User-Domain-Name: Default
        X-User-Id: 91d732b65831491d8bd952b3111e62dd
        X-User-Name: admin
        ======================================================================================
        """
        
        # Identify the action, its arguments, and the requested
        # content type
        """
        从request.environ中获取要执行的action方法；
        @@@@注：看看action_args中的元素是如何获取的何时获取的；
        """
        action_args = self.get_action_args(request.environ)
        action = action_args.pop('action', None)
        content_type, body = self.get_body(request)
        accept = request.best_match_content_type()
        """
        ======================================================================================
        action_args = {'action': u'detail', 
                       'project_id': u'4537aca4a4a4462fa4c59ad5b5581f00'}
        action = detail
        content_type = None
        body = 
        accept = application/json
        
        request.environ:
        'wsgiorg.routing_args': (<routes.util.URLGenerator object at 0x4e8da50>, 
                                {'action': u'detail', 
                                 'controller': <nova.api.openstack.wsgi.Resource object at 0x3d5cf90>, 
                                 'project_id': u'2a3cc2062e154e148b50e79ed3736e4a'})
        ======================================================================================
        """
        
        
        # NOTE(Vek): Splitting the function up this way allows for
        #            auditing by external tools that wrap the existing
        #            function.  If we try to audit __call__(), we can
        #            run into troubles due to the @webob.dec.wsgify()
        #            decorator.
        """
        来看方法_process_stack，这个方法主要完成了请求信息完整的执行过程；
        """
        """
        return:
        ======================================================================================
        response = 200 OK
        Content-Type: application/json
        Content-Length: 1520
        x-compute-request-id: req-712c9eb8-55e4-415a-ba36-436ef8f17e87
        
        {"servers": [{"status": "SHUTOFF", "updated": "2015-03-17T16:59:39Z", "hostId": "80edf4278faf2e792eedcf39ba7cda12df2169bdaad7ea118081e07f", "OS-EXT-SRV-ATTR:host": "node02.shinian.com", "addresses": {}, "links": [{"href": "http://172.21.6.180:8774/v2/2a3cc2062e154e148b50e79ed3736e4a/servers/770ae6a2-f7dc-4f90-af0e-361bb22ce9cc", "rel": "self"}, {"href": "http://172.21.6.180:8774/2a3cc2062e154e148b50e79ed3736e4a/servers/770ae6a2-f7dc-4f90-af0e-361bb22ce9cc", "rel": "bookmark"}], "key_name": "oskey", "image": {"id": "d407bd3e-aa1c-49ea-bc84-00584182b283", "links": [{"href": "http://172.21.6.180:8774/2a3cc2062e154e148b50e79ed3736e4a/images/d407bd3e-aa1c-49ea-bc84-00584182b283", "rel": "bookmark"}]}, "OS-EXT-STS:task_state": null, "OS-EXT-STS:vm_state": "stopped", "OS-EXT-SRV-ATTR:instance_name": "instance-00000002", "OS-SRV-USG:launched_at": "2015-03-17T15:25:31.000000", "OS-EXT-SRV-ATTR:hypervisor_hostname": "node02.shinian.com", "flavor": {"id": "1", "links": [{"href": "http://172.21.6.180:8774/2a3cc2062e154e148b50e79ed3736e4a/flavors/1", "rel": "bookmark"}]}, "id": "770ae6a2-f7dc-4f90-af0e-361bb22ce9cc", "OS-SRV-USG:terminated_at": null, "OS-EXT-AZ:availability_zone": "nova", "user_id": "c01f7e46dfe84393bc214626edebc959", "name": "test0", "created": "2015-03-17T15:24:46Z", "tenant_id": "2a3cc2062e154e148b50e79ed3736e4a", "OS-DCF:diskConfig": "MANUAL", "os-extended-volumes:volumes_attached": [], "accessIPv4": "", "accessIPv6": "", "OS-EXT-STS:power_state": 4, "config_drive": "", "metadata": {}}]}
        ======================================================================================
        """
        return self._process_stack(request, action, action_args,
                               content_type, body, accept)

    def _process_stack(self, request, action, action_args,
                       content_type, body, accept):
        """
        Implement the processing stack.
        """
        """
        ======================================================================================
        request = GET /v2/4537aca4a4a4462fa4c59ad5b5581f00/servers/detail HTTP/1.0
        Accept: application/json
        Accept-Encoding: gzip, deflate, compress
        Content-Length: 0
        Content-Type: text/plain
        Host: 172.21.7.40:8774
        User-Agent: python-novaclient
        X-Auth-Project-Id: admin
        X-Auth-Token: MIIT9wYJKoZIhvcNAQcCoIIT6DCCE+QCAQExCTAHBgUrDgMCGjCCEk0GCSqGSIb3DQEHAaCCEj4EghI6eyJhY2Nlc3MiOiB7InRva2VuIjogeyJpc3N1ZWRfYXQiOiAiMjAxNS0wMy0xNlQwMzozNjoyNS43OTc5MjAiLCAiZXhwaXJlcyI6ICIyMDE1LTAzLTE2VDA0OjM2OjI1WiIsICJpZCI6ICJwbGFjZWhvbGRlciIsICJ0ZW5hbnQiOiB7ImRlc2NyaXB0aW9uIjogImFkbWluIHRlbmFudCIsICJlbmFibGVkIjogdHJ1ZSwgImlkIjogIjQ1MzdhY2E0YTRhNDQ2MmZhNGM1OWFkNWI1NTgxZjAwIiwgIm5hbWUiOiAiYWRtaW4ifX0sICJzZXJ2aWNlQ2F0YWxvZyI6IFt7ImVuZHBvaW50cyI6IFt7ImFkbWluVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo4Nzc0L3YyLzQ1MzdhY2E0YTRhNDQ2MmZhNGM1OWFkNWI1NTgxZjAwIiwgInJlZ2lvbiI6ICJSZWdpb25PbmUiLCAiaW50ZXJuYWxVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjg3NzQvdjIvNDUzN2FjYTRhNGE0NDYyZmE0YzU5YWQ1YjU1ODFmMDAiLCAiaWQiOiAiMTZiMTVjYzVmZjUwNGNiODlmNTg2NjRlMjdhNjljNjkiLCAicHVibGljVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo4Nzc0L3YyLzQ1MzdhY2E0YTRhNDQ2MmZhNGM1OWFkNWI1NTgxZjAwIn1dLCAiZW5kcG9pbnRzX2xpbmtzIjogW10sICJ0eXBlIjogImNvbXB1dGUiLCAibmFtZSI6ICJub3ZhIn0sIHsiZW5kcG9pbnRzIjogW3siYWRtaW5VUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjk2OTYvIiwgInJlZ2lvbiI6ICJSZWdpb25PbmUiLCAiaW50ZXJuYWxVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjk2OTYvIiwgImlkIjogIjFiMjkzYTgxNjk2YjRiN2Y4OTZlYWQ0NjIyYTFjMmExIiwgInB1YmxpY1VSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6OTY5Ni8ifV0sICJlbmRwb2ludHNfbGlua3MiOiBbXSwgInR5cGUiOiAibmV0d29yayIsICJuYW1lIjogIm5ldXRyb24ifSwgeyJlbmRwb2ludHMiOiBbeyJhZG1pblVSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODc3Ni92Mi80NTM3YWNhNGE0YTQ0NjJmYTRjNTlhZDViNTU4MWYwMCIsICJyZWdpb24iOiAiUmVnaW9uT25lIiwgImludGVybmFsVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo4Nzc2L3YyLzQ1MzdhY2E0YTRhNDQ2MmZhNGM1OWFkNWI1NTgxZjAwIiwgImlkIjogIjNhNzY3OWNjZTdkZjRhY2ZhMTZiM2NhNTJkZGNmYzgyIiwgInB1YmxpY1VSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODc3Ni92Mi80NTM3YWNhNGE0YTQ0NjJmYTRjNTlhZDViNTU4MWYwMCJ9XSwgImVuZHBvaW50c19saW5rcyI6IFtdLCAidHlwZSI6ICJ2b2x1bWV2MiIsICJuYW1lIjogImNpbmRlcnYyIn0sIHsiZW5kcG9pbnRzIjogW3siYWRtaW5VUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjg3NzQvdjMiLCAicmVnaW9uIjogIlJlZ2lvbk9uZSIsICJpbnRlcm5hbFVSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODc3NC92MyIsICJpZCI6ICIwYmIxZDFiODhhZmU0MGRhOTNiY2IxNTg0Y2ExN2ZiOSIsICJwdWJsaWNVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjg3NzQvdjMifV0sICJlbmRwb2ludHNfbGlua3MiOiBbXSwgInR5cGUiOiAiY29tcHV0ZXYzIiwgIm5hbWUiOiAibm92YXYzIn0sIHsiZW5kcG9pbnRzIjogW3siYWRtaW5VUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjgwODAiLCAicmVnaW9uIjogIlJlZ2lvbk9uZSIsICJpbnRlcm5hbFVSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODA4MCIsICJpZCI6ICIxZTMyZTE3MmU3OWM0YzVhYTZiNWM3ZjhkNzVhZjRmYiIsICJwdWJsaWNVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjgwODAifV0sICJlbmRwb2ludHNfbGlua3MiOiBbXSwgInR5cGUiOiAiczMiLCAibmFtZSI6ICJzd2lmdF9zMyJ9LCB7ImVuZHBvaW50cyI6IFt7ImFkbWluVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo5MjkyIiwgInJlZ2lvbiI6ICJSZWdpb25PbmUiLCAiaW50ZXJuYWxVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjkyOTIiLCAiaWQiOiAiM2QxYzc5MjY1MWEwNDljNWE2MWUzNWJmZWZjNGM4OGIiLCAicHVibGljVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo5MjkyIn1dLCAiZW5kcG9pbnRzX2xpbmtzIjogW10sICJ0eXBlIjogImltYWdlIiwgIm5hbWUiOiAiZ2xhbmNlIn0sIHsiZW5kcG9pbnRzIjogW3siYWRtaW5VUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjg3NzciLCAicmVnaW9uIjogIlJlZ2lvbk9uZSIsICJpbnRlcm5hbFVSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODc3NyIsICJpZCI6ICIzOWE0YzA2NDIzYTg0OTNjOTI4ZGExOGY0YTVjY2MxZiIsICJwdWJsaWNVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjg3NzcifV0sICJlbmRwb2ludHNfbGlua3MiOiBbXSwgInR5cGUiOiAibWV0ZXJpbmciLCAibmFtZSI6ICJjZWlsb21ldGVyIn0sIHsiZW5kcG9pbnRzIjogW3siYWRtaW5VUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjgwMDAvdjEvIiwgInJlZ2lvbiI6ICJSZWdpb25PbmUiLCAiaW50ZXJuYWxVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjgwMDAvdjEvIiwgImlkIjogIjU1NzBiOGY4MTE0OTRlMWI5NTVkYjZlNTAzZGYyYWZkIiwgInB1YmxpY1VSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODAwMC92MS8ifV0sICJlbmRwb2ludHNfbGlua3MiOiBbXSwgInR5cGUiOiAiY2xvdWRmb3JtYXRpb24iLCAibmFtZSI6ICJoZWF0LWNmbiJ9LCB7ImVuZHBvaW50cyI6IFt7ImFkbWluVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo4Nzc2L3YxLzQ1MzdhY2E0YTRhNDQ2MmZhNGM1OWFkNWI1NTgxZjAwIiwgInJlZ2lvbiI6ICJSZWdpb25PbmUiLCAiaW50ZXJuYWxVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjg3NzYvdjEvNDUzN2FjYTRhNGE0NDYyZmE0YzU5YWQ1YjU1ODFmMDAiLCAiaWQiOiAiMGExYzhkYTRmMTU2NDk1YWFkMjEzMGUyYzA2OTE5ODIiLCAicHVibGljVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo4Nzc2L3YxLzQ1MzdhY2E0YTRhNDQ2MmZhNGM1OWFkNWI1NTgxZjAwIn1dLCAiZW5kcG9pbnRzX2xpbmtzIjogW10sICJ0eXBlIjogInZvbHVtZSIsICJuYW1lIjogImNpbmRlciJ9LCB7ImVuZHBvaW50cyI6IFt7ImFkbWluVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo4NzczL3NlcnZpY2VzL0FkbWluIiwgInJlZ2lvbiI6ICJSZWdpb25PbmUiLCAiaW50ZXJuYWxVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjg3NzMvc2VydmljZXMvQ2xvdWQiLCAiaWQiOiAiMDMzZjY3ZTk1MDBjNDljYThmOGIxODkzZTJhN2VkYWYiLCAicHVibGljVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo4NzczL3NlcnZpY2VzL0Nsb3VkIn1dLCAiZW5kcG9pbnRzX2xpbmtzIjogW10sICJ0eXBlIjogImVjMiIsICJuYW1lIjogIm5vdmFfZWMyIn0sIHsiZW5kcG9pbnRzIjogW3siYWRtaW5VUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjgwMDQvdjEvNDUzN2FjYTRhNGE0NDYyZmE0YzU5YWQ1YjU1ODFmMDAiLCAicmVnaW9uIjogIlJlZ2lvbk9uZSIsICJpbnRlcm5hbFVSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODAwNC92MS80NTM3YWNhNGE0YTQ0NjJmYTRjNTlhZDViNTU4MWYwMCIsICJpZCI6ICI0YmViNjQ0MjUzYWU0NzdmOWU5NDk2ZWVkZDEwOTNhNSIsICJwdWJsaWNVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjgwMDQvdjEvNDUzN2FjYTRhNGE0NDYyZmE0YzU5YWQ1YjU1ODFmMDAifV0sICJlbmRwb2ludHNfbGlua3MiOiBbXSwgInR5cGUiOiAib3JjaGVzdHJhdGlvbiIsICJuYW1lIjogImhlYXQifSwgeyJlbmRwb2ludHMiOiBbeyJhZG1pblVSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODA4MC8iLCAicmVnaW9uIjogIlJlZ2lvbk9uZSIsICJpbnRlcm5hbFVSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODA4MC92MS9BVVRIXzQ1MzdhY2E0YTRhNDQ2MmZhNGM1OWFkNWI1NTgxZjAwIiwgImlkIjogIjNhMTA2MzU0MjYxMDQzMjk5YTVkMjQ3ZTVmMjU5NGQyIiwgInB1YmxpY1VSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODA4MC92MS9BVVRIXzQ1MzdhY2E0YTRhNDQ2MmZhNGM1OWFkNWI1NTgxZjAwIn1dLCAiZW5kcG9pbnRzX2xpbmtzIjogW10sICJ0eXBlIjogIm9iamVjdC1zdG9yZSIsICJuYW1lIjogInN3aWZ0In0sIHsiZW5kcG9pbnRzIjogW3siYWRtaW5VUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjM1MzU3L3YyLjAiLCAicmVnaW9uIjogIlJlZ2lvbk9uZSIsICJpbnRlcm5hbFVSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6NTAwMC92Mi4wIiwgImlkIjogIjVjNGVlN2MzMTE4NDQyNGM5NDJhMWM1MjgxODU3MmZiIiwgInB1YmxpY1VSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6NTAwMC92Mi4wIn1dLCAiZW5kcG9pbnRzX2xpbmtzIjogW10sICJ0eXBlIjogImlkZW50aXR5IiwgIm5hbWUiOiAia2V5c3RvbmUifV0sICJ1c2VyIjogeyJ1c2VybmFtZSI6ICJhZG1pbiIsICJyb2xlc19saW5rcyI6IFtdLCAiaWQiOiAiOTFkNzMyYjY1ODMxNDkxZDhiZDk1MmIzMTExZTYyZGQiLCAicm9sZXMiOiBbeyJuYW1lIjogImhlYXRfc3RhY2tfb3duZXIifSwgeyJuYW1lIjogIl9tZW1iZXJfIn0sIHsibmFtZSI6ICJhZG1pbiJ9XSwgIm5hbWUiOiAiYWRtaW4ifSwgIm1ldGFkYXRhIjogeyJpc19hZG1pbiI6IDAsICJyb2xlcyI6IFsiZDlmZGVlODI1NjE3NGJlNWE3MmFjZGZmNDNkM2VkZDMiLCAiOWZlMmZmOWVlNDM4NGIxODk0YTkwODc4ZDNlOTJiYWIiLCAiN2E1ZTg5MmFiYTE5NDI3NWI3ZjQxZWM4Njg2ZDUwOGYiXX19fTGCAYEwggF9AgEBMFwwVzELMAkGA1UEBhMCVVMxDjAMBgNVBAgMBVVuc2V0MQ4wDAYDVQQHDAVVbnNldDEOMAwGA1UECgwFVW5zZXQxGDAWBgNVBAMMD3d3dy5leGFtcGxlLmNvbQIBATAHBgUrDgMCGjANBgkqhkiG9w0BAQEFAASCAQBQf7jWBgs5NTmDg+GrOkg0QwZYl2FIs8QEEq+cUGKHpZw47RuWYTpxth3r7YBWXHuVkj41o3y44r8X+KWqMh0-gRloztQQs5j+OjmnnTevqcU7nMb-mIInEflwr6OfVG0n7bwmb8880637z658op-30jnD-ls129Zwy4jAapXblYsFnPU6i8C-3CCzqdP7kd3F1DZmBVwxntuCFXkNCIiD1d-FZnGgdp1l4ruUfX5JffWAkaP77LfmVz3McsxSXLF4n13dF+B7O29bAz+s+TOvS+QtPjh57kyZoR9fPAIDQNomZYOJd0M9b0XMDNFoi60p47rzeUoZyTkZKsROSI9W
        X-Domain-Id: None
        X-Domain-Name: None
        X-Identity-Status: Confirmed
        X-Project-Domain-Id: default
        X-Project-Domain-Name: Default
        X-Project-Id: 4537aca4a4a4462fa4c59ad5b5581f00
        X-Project-Name: admin
        X-Role: heat_stack_owner,_member_,admin
        X-Roles: heat_stack_owner,_member_,admin
        X-Service-Catalog: [{"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:8774/v2/4537aca4a4a4462fa4c59ad5b5581f00", "region": "RegionOne", "publicURL": "http://172.21.7.40:8774/v2/4537aca4a4a4462fa4c59ad5b5581f00", "internalURL": "http://172.21.7.40:8774/v2/4537aca4a4a4462fa4c59ad5b5581f00", "id": "16b15cc5ff504cb89f58664e27a69c69"}], "type": "compute", "name": "nova"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:9696/", "region": "RegionOne", "publicURL": "http://172.21.7.40:9696/", "internalURL": "http://172.21.7.40:9696/", "id": "1b293a81696b4b7f896ead4622a1c2a1"}], "type": "network", "name": "neutron"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:8776/v2/4537aca4a4a4462fa4c59ad5b5581f00", "region": "RegionOne", "publicURL": "http://172.21.7.40:8776/v2/4537aca4a4a4462fa4c59ad5b5581f00", "internalURL": "http://172.21.7.40:8776/v2/4537aca4a4a4462fa4c59ad5b5581f00", "id": "3a7679cce7df4acfa16b3ca52ddcfc82"}], "type": "volumev2", "name": "cinderv2"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:8774/v3", "region": "RegionOne", "publicURL": "http://172.21.7.40:8774/v3", "internalURL": "http://172.21.7.40:8774/v3", "id": "0bb1d1b88afe40da93bcb1584ca17fb9"}], "type": "computev3", "name": "novav3"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:8080", "region": "RegionOne", "publicURL": "http://172.21.7.40:8080", "internalURL": "http://172.21.7.40:8080", "id": "1e32e172e79c4c5aa6b5c7f8d75af4fb"}], "type": "s3", "name": "swift_s3"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:9292", "region": "RegionOne", "publicURL": "http://172.21.7.40:9292", "internalURL": "http://172.21.7.40:9292", "id": "3d1c792651a049c5a61e35bfefc4c88b"}], "type": "image", "name": "glance"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:8777", "region": "RegionOne", "publicURL": "http://172.21.7.40:8777", "internalURL": "http://172.21.7.40:8777", "id": "39a4c06423a8493c928da18f4a5ccc1f"}], "type": "metering", "name": "ceilometer"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:8000/v1/", "region": "RegionOne", "publicURL": "http://172.21.7.40:8000/v1/", "internalURL": "http://172.21.7.40:8000/v1/", "id": "5570b8f811494e1b955db6e503df2afd"}], "type": "cloudformation", "name": "heat-cfn"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:8776/v1/4537aca4a4a4462fa4c59ad5b5581f00", "region": "RegionOne", "publicURL": "http://172.21.7.40:8776/v1/4537aca4a4a4462fa4c59ad5b5581f00", "internalURL": "http://172.21.7.40:8776/v1/4537aca4a4a4462fa4c59ad5b5581f00", "id": "0a1c8da4f156495aad2130e2c0691982"}], "type": "volume", "name": "cinder"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:8773/services/Admin", "region": "RegionOne", "publicURL": "http://172.21.7.40:8773/services/Cloud", "internalURL": "http://172.21.7.40:8773/services/Cloud", "id": "033f67e9500c49ca8f8b1893e2a7edaf"}], "type": "ec2", "name": "nova_ec2"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:8004/v1/4537aca4a4a4462fa4c59ad5b5581f00", "region": "RegionOne", "publicURL": "http://172.21.7.40:8004/v1/4537aca4a4a4462fa4c59ad5b5581f00", "internalURL": "http://172.21.7.40:8004/v1/4537aca4a4a4462fa4c59ad5b5581f00", "id": "4beb644253ae477f9e9496eedd1093a5"}], "type": "orchestration", "name": "heat"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:8080/", "region": "RegionOne", "publicURL": "http://172.21.7.40:8080/v1/AUTH_4537aca4a4a4462fa4c59ad5b5581f00", "internalURL": "http://172.21.7.40:8080/v1/AUTH_4537aca4a4a4462fa4c59ad5b5581f00", "id": "3a106354261043299a5d247e5f2594d2"}], "type": "object-store", "name": "swift"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:35357/v2.0", "region": "RegionOne", "publicURL": "http://172.21.7.40:5000/v2.0", "internalURL": "http://172.21.7.40:5000/v2.0", "id": "5c4ee7c31184424c942a1c52818572fb"}], "type": "identity", "name": "keystone"}]
        X-Tenant: admin
        X-Tenant-Id: 4537aca4a4a4462fa4c59ad5b5581f00
        X-Tenant-Name: admin
        X-User: admin
        X-User-Domain-Id: default
        X-User-Domain-Name: Default
        X-User-Id: 91d732b65831491d8bd952b3111e62dd
        X-User-Name: admin
        
        action = detail
        action_args = {'project_id': u'4537aca4a4a4462fa4c59ad5b5581f00'}
        content_type = None
        body = 
        accept = application/json
        ======================================================================================
        """

        # Get the implementing method
        """
        这条语句实现的功能是根据request确定要执行的action方法以及相关的扩展方法；
        
        如果action不等于'action'，则：
        meth = action
        meth_extensions = self.wsgi_extensions.get(action, [])
        即从@wsgi.extends修饰的没有action参数的扩展方法中选取，作为meth对应的扩展方法；
        
        如果action等于'action'，则：
        meth = self.wsgi_actions[action_name]
        即从@wsgi.actions修饰的扩展方法中选取，作为meth方法；
        meth_extensions = self.wsgi_action_extensions.get(action_name, [])
        即从@wsgi.extends修饰的有action参数的扩展方法中选取，作为meth对应的扩展方法；
        """
        try:
            meth, extensions = self.get_method(request, action,
                                               content_type, body)
        except (AttributeError, TypeError):
            return Fault(webob.exc.HTTPNotFound())
        except KeyError as ex:
            msg = _("There is no such action: %s") % ex.args[0]
            return Fault(webob.exc.HTTPBadRequest(explanation=msg))
        except exception.MalformedRequestBody:
            msg = _("Malformed request body")
            return Fault(webob.exc.HTTPBadRequest(explanation=msg))

        if body:
            msg = _("Action: '%(action)s', body: "
                    "%(body)s") % {'action': action,
                                   'body': unicode(body, 'utf-8')}
            LOG.debug(logging.mask_password(msg))
        LOG.debug(_("Calling method '%(meth)s' (Content-type='%(ctype)s', "
                    "Accept='%(accept)s')"),
                  {'meth': str(meth),
                   'ctype': content_type,
                   'accept': accept})

        # Now, deserialize the request body...
        try:
            contents = {}
            
            """
            如果method为POST或者PUT的话，req中就会有body部分；
            如果method不是POST和PUT的话，req中就不会有body部分；
            
            如果req中有body部分，则需要进行反序列化操作；
            （这里应该是对应于novaclient中body部分的序列化操作；）
            获取指定的反序列化方法；
            根据确定的反序列化方法对body进行反序列化的实现；
            
            req中的body部分反序列化输出示例：
            contents = {'body': {u'volume': {u'status': u'creating', 
                                  u'user_id': None, 
                                  u'imageRef': None, 
                                  u'availability_zone': None, 
                                  u'attach_status': u'detached', 
                                  u'display_description': None, 
                                  u'metadata': {}, 
                                  u'source_volid': None, 
                                  u'snapshot_id': None, 
                                  u'display_name': u'shinian01', 
                                  u'project_id': None, 
                                  u'volume_type': None, 
                                  u'size': 1}}}
            """
            if self._should_have_body(request):
                #allow empty body with PUT and POST
                if request.content_length == 0:
                    contents = {'body': None}
                else:
                    contents = self.deserialize(meth, content_type, body)
        except exception.InvalidContentType:
            msg = _("Unsupported Content-Type")
            return Fault(webob.exc.HTTPBadRequest(explanation=msg))
        except exception.MalformedRequestBody:
            msg = _("Malformed request body")
            return Fault(webob.exc.HTTPBadRequest(explanation=msg))

        # Update the action args
        """
        更新action_args；
        contents = {'body': {u'volume': {u'status': u'creating', 
                                  u'user_id': None, 
                                  u'imageRef': None, 
                                  u'availability_zone': None, 
                                  u'attach_status': u'detached', 
                                  u'display_description': None, 
                                  u'metadata': {}, 
                                  u'source_volid': None, 
                                  u'snapshot_id': None, 
                                  u'display_name': u'shinian01', 
                                  u'project_id': None, 
                                  u'volume_type': None, 
                                  u'size': 1}}}
        """
        action_args.update(contents)

        project_id = action_args.pop("project_id", None)
        context = request.environ.get('nova.context')
        if (context and project_id and (project_id != context.project_id)):
            msg = _("Malformed request URL: URL's project_id '%(project_id)s'"
                    " doesn't match Context's project_id"
                    " '%(context_project_id)s'") % \
                    {'project_id': project_id,
                     'context_project_id': context.project_id}
            return Fault(webob.exc.HTTPBadRequest(explanation=msg))

        # Run pre-processing extensions
        """
        扩展方法的执行顺序：
        ======================================================================================
        method SecurityGroupsOutputController.detail
        获取resp_obj中所有虚拟机实例的安全组的相关信息，将其写入resp_obj中；
        ======================================================================================
        method keypairs.Controller.detail
        获取resp_obj中每个虚拟机实例的key_name值，将其写入resp_obj中；
        ======================================================================================
        method hide_server_addresses.Controller.detail
        实现在resp_obj中隐藏虚拟机实例的地址；
        ======================================================================================
        method ExtendedVolumesController.detail
        获取resp_obj中每个虚拟机实例所挂载的所有的卷id值，将其写入resp_obj中；
        ======================================================================================
        method config_drive.Controller.detail
        获取resp_obj中每个虚拟机实例的config_drive值，将其写入resp_obj中；
        ======================================================================================
        method ServerUsageController.detail
        获取resp_obj中每个虚拟机实例的启动和中止的时间等值，将其写入resp_obj中；
        ======================================================================================
        method ExtendedStatusController.detail
        获取resp_obj中每个虚拟机实例的task_state/vm_state/power_state等值，将其写入resp_obj中；
        ======================================================================================
        method ExtendedServerAttributesController.detail
        获取resp_obj中每个虚拟机实例的hypervisor_hostname/instance_name/host等值，将其写入resp_obj中；
        ======================================================================================
        method ExtendedIpsMacController.detail
        获取resp_obj中每个虚拟机实例的所有mac_addr的值，将其写入resp_obj中；
        ======================================================================================
        method ExtendedIpsController.detail
        获取resp_obj中每个虚拟机实例的所有ip_type的值，将其写入resp_obj中；
        ======================================================================================
        method ExtendedAZController.detail
        获取resp_obj中每个虚拟机实例的availability_zone的值，将其写入resp_obj中；
        ======================================================================================
        method ServerDiskConfigController.detail
        获取resp_obj中每个虚拟机实例的diskConfig的值，将其写入resp_obj中；
        ======================================================================================
        """
        response, post = self.pre_process_extensions(extensions,
                                                     request, action_args)
        """
        ======================================================================================
        response = None
        post = <listreverseiterator object at 0x2369a10>
        ======================================================================================
        """

        if not response:
            try:
                with ResourceExceptionHandler():
                    action_result = self.dispatch(meth, request, action_args)
                    """
                    ======================================================================================
                    meth = <bound method Controller.detail of <nova.api.openstack.compute.servers.Controller object at 0x29b0e50>>
                    action_args = {}
                    
                    request = GET /v2/4537aca4a4a4462fa4c59ad5b5581f00/servers/detail HTTP/1.0
                    Accept: application/json
                    Accept-Encoding: gzip, deflate, compress
                    Content-Type: text/plain
                    Host: 172.21.7.40:8774
                    User-Agent: python-novaclient
                    X-Auth-Project-Id: admin
                    X-Auth-Token: MIIT9wYJKoZIhvcNAQcCoIIT6DCCE+QCAQExCTAHBgUrDgMCGjCCEk0GCSqGSIb3DQEHAaCCEj4EghI6eyJhY2Nlc3MiOiB7InRva2VuIjogeyJpc3N1ZWRfYXQiOiAiMjAxNS0wMy0xOFQwNzoyMjo0OS42MTMzMzgiLCAiZXhwaXJlcyI6ICIyMDE1LTAzLTE4VDA4OjIyOjQ5WiIsICJpZCI6ICJwbGFjZWhvbGRlciIsICJ0ZW5hbnQiOiB7ImRlc2NyaXB0aW9uIjogImFkbWluIHRlbmFudCIsICJlbmFibGVkIjogdHJ1ZSwgImlkIjogIjQ1MzdhY2E0YTRhNDQ2MmZhNGM1OWFkNWI1NTgxZjAwIiwgIm5hbWUiOiAiYWRtaW4ifX0sICJzZXJ2aWNlQ2F0YWxvZyI6IFt7ImVuZHBvaW50cyI6IFt7ImFkbWluVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo4Nzc0L3YyLzQ1MzdhY2E0YTRhNDQ2MmZhNGM1OWFkNWI1NTgxZjAwIiwgInJlZ2lvbiI6ICJSZWdpb25PbmUiLCAiaW50ZXJuYWxVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjg3NzQvdjIvNDUzN2FjYTRhNGE0NDYyZmE0YzU5YWQ1YjU1ODFmMDAiLCAiaWQiOiAiMTZiMTVjYzVmZjUwNGNiODlmNTg2NjRlMjdhNjljNjkiLCAicHVibGljVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo4Nzc0L3YyLzQ1MzdhY2E0YTRhNDQ2MmZhNGM1OWFkNWI1NTgxZjAwIn1dLCAiZW5kcG9pbnRzX2xpbmtzIjogW10sICJ0eXBlIjogImNvbXB1dGUiLCAibmFtZSI6ICJub3ZhIn0sIHsiZW5kcG9pbnRzIjogW3siYWRtaW5VUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjk2OTYvIiwgInJlZ2lvbiI6ICJSZWdpb25PbmUiLCAiaW50ZXJuYWxVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjk2OTYvIiwgImlkIjogIjFiMjkzYTgxNjk2YjRiN2Y4OTZlYWQ0NjIyYTFjMmExIiwgInB1YmxpY1VSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6OTY5Ni8ifV0sICJlbmRwb2ludHNfbGlua3MiOiBbXSwgInR5cGUiOiAibmV0d29yayIsICJuYW1lIjogIm5ldXRyb24ifSwgeyJlbmRwb2ludHMiOiBbeyJhZG1pblVSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODc3Ni92Mi80NTM3YWNhNGE0YTQ0NjJmYTRjNTlhZDViNTU4MWYwMCIsICJyZWdpb24iOiAiUmVnaW9uT25lIiwgImludGVybmFsVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo4Nzc2L3YyLzQ1MzdhY2E0YTRhNDQ2MmZhNGM1OWFkNWI1NTgxZjAwIiwgImlkIjogIjNhNzY3OWNjZTdkZjRhY2ZhMTZiM2NhNTJkZGNmYzgyIiwgInB1YmxpY1VSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODc3Ni92Mi80NTM3YWNhNGE0YTQ0NjJmYTRjNTlhZDViNTU4MWYwMCJ9XSwgImVuZHBvaW50c19saW5rcyI6IFtdLCAidHlwZSI6ICJ2b2x1bWV2MiIsICJuYW1lIjogImNpbmRlcnYyIn0sIHsiZW5kcG9pbnRzIjogW3siYWRtaW5VUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjg3NzQvdjMiLCAicmVnaW9uIjogIlJlZ2lvbk9uZSIsICJpbnRlcm5hbFVSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODc3NC92MyIsICJpZCI6ICIwYmIxZDFiODhhZmU0MGRhOTNiY2IxNTg0Y2ExN2ZiOSIsICJwdWJsaWNVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjg3NzQvdjMifV0sICJlbmRwb2ludHNfbGlua3MiOiBbXSwgInR5cGUiOiAiY29tcHV0ZXYzIiwgIm5hbWUiOiAibm92YXYzIn0sIHsiZW5kcG9pbnRzIjogW3siYWRtaW5VUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjgwODAiLCAicmVnaW9uIjogIlJlZ2lvbk9uZSIsICJpbnRlcm5hbFVSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODA4MCIsICJpZCI6ICIxZTMyZTE3MmU3OWM0YzVhYTZiNWM3ZjhkNzVhZjRmYiIsICJwdWJsaWNVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjgwODAifV0sICJlbmRwb2ludHNfbGlua3MiOiBbXSwgInR5cGUiOiAiczMiLCAibmFtZSI6ICJzd2lmdF9zMyJ9LCB7ImVuZHBvaW50cyI6IFt7ImFkbWluVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo5MjkyIiwgInJlZ2lvbiI6ICJSZWdpb25PbmUiLCAiaW50ZXJuYWxVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjkyOTIiLCAiaWQiOiAiM2QxYzc5MjY1MWEwNDljNWE2MWUzNWJmZWZjNGM4OGIiLCAicHVibGljVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo5MjkyIn1dLCAiZW5kcG9pbnRzX2xpbmtzIjogW10sICJ0eXBlIjogImltYWdlIiwgIm5hbWUiOiAiZ2xhbmNlIn0sIHsiZW5kcG9pbnRzIjogW3siYWRtaW5VUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjg3NzciLCAicmVnaW9uIjogIlJlZ2lvbk9uZSIsICJpbnRlcm5hbFVSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODc3NyIsICJpZCI6ICIzOWE0YzA2NDIzYTg0OTNjOTI4ZGExOGY0YTVjY2MxZiIsICJwdWJsaWNVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjg3NzcifV0sICJlbmRwb2ludHNfbGlua3MiOiBbXSwgInR5cGUiOiAibWV0ZXJpbmciLCAibmFtZSI6ICJjZWlsb21ldGVyIn0sIHsiZW5kcG9pbnRzIjogW3siYWRtaW5VUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjgwMDAvdjEvIiwgInJlZ2lvbiI6ICJSZWdpb25PbmUiLCAiaW50ZXJuYWxVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjgwMDAvdjEvIiwgImlkIjogIjU1NzBiOGY4MTE0OTRlMWI5NTVkYjZlNTAzZGYyYWZkIiwgInB1YmxpY1VSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODAwMC92MS8ifV0sICJlbmRwb2ludHNfbGlua3MiOiBbXSwgInR5cGUiOiAiY2xvdWRmb3JtYXRpb24iLCAibmFtZSI6ICJoZWF0LWNmbiJ9LCB7ImVuZHBvaW50cyI6IFt7ImFkbWluVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo4Nzc2L3YxLzQ1MzdhY2E0YTRhNDQ2MmZhNGM1OWFkNWI1NTgxZjAwIiwgInJlZ2lvbiI6ICJSZWdpb25PbmUiLCAiaW50ZXJuYWxVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjg3NzYvdjEvNDUzN2FjYTRhNGE0NDYyZmE0YzU5YWQ1YjU1ODFmMDAiLCAiaWQiOiAiMGExYzhkYTRmMTU2NDk1YWFkMjEzMGUyYzA2OTE5ODIiLCAicHVibGljVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo4Nzc2L3YxLzQ1MzdhY2E0YTRhNDQ2MmZhNGM1OWFkNWI1NTgxZjAwIn1dLCAiZW5kcG9pbnRzX2xpbmtzIjogW10sICJ0eXBlIjogInZvbHVtZSIsICJuYW1lIjogImNpbmRlciJ9LCB7ImVuZHBvaW50cyI6IFt7ImFkbWluVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo4NzczL3NlcnZpY2VzL0FkbWluIiwgInJlZ2lvbiI6ICJSZWdpb25PbmUiLCAiaW50ZXJuYWxVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjg3NzMvc2VydmljZXMvQ2xvdWQiLCAiaWQiOiAiMDMzZjY3ZTk1MDBjNDljYThmOGIxODkzZTJhN2VkYWYiLCAicHVibGljVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo4NzczL3NlcnZpY2VzL0Nsb3VkIn1dLCAiZW5kcG9pbnRzX2xpbmtzIjogW10sICJ0eXBlIjogImVjMiIsICJuYW1lIjogIm5vdmFfZWMyIn0sIHsiZW5kcG9pbnRzIjogW3siYWRtaW5VUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjgwMDQvdjEvNDUzN2FjYTRhNGE0NDYyZmE0YzU5YWQ1YjU1ODFmMDAiLCAicmVnaW9uIjogIlJlZ2lvbk9uZSIsICJpbnRlcm5hbFVSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODAwNC92MS80NTM3YWNhNGE0YTQ0NjJmYTRjNTlhZDViNTU4MWYwMCIsICJpZCI6ICI0YmViNjQ0MjUzYWU0NzdmOWU5NDk2ZWVkZDEwOTNhNSIsICJwdWJsaWNVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjgwMDQvdjEvNDUzN2FjYTRhNGE0NDYyZmE0YzU5YWQ1YjU1ODFmMDAifV0sICJlbmRwb2ludHNfbGlua3MiOiBbXSwgInR5cGUiOiAib3JjaGVzdHJhdGlvbiIsICJuYW1lIjogImhlYXQifSwgeyJlbmRwb2ludHMiOiBbeyJhZG1pblVSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODA4MC8iLCAicmVnaW9uIjogIlJlZ2lvbk9uZSIsICJpbnRlcm5hbFVSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODA4MC92MS9BVVRIXzQ1MzdhY2E0YTRhNDQ2MmZhNGM1OWFkNWI1NTgxZjAwIiwgImlkIjogIjNhMTA2MzU0MjYxMDQzMjk5YTVkMjQ3ZTVmMjU5NGQyIiwgInB1YmxpY1VSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODA4MC92MS9BVVRIXzQ1MzdhY2E0YTRhNDQ2MmZhNGM1OWFkNWI1NTgxZjAwIn1dLCAiZW5kcG9pbnRzX2xpbmtzIjogW10sICJ0eXBlIjogIm9iamVjdC1zdG9yZSIsICJuYW1lIjogInN3aWZ0In0sIHsiZW5kcG9pbnRzIjogW3siYWRtaW5VUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjM1MzU3L3YyLjAiLCAicmVnaW9uIjogIlJlZ2lvbk9uZSIsICJpbnRlcm5hbFVSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6NTAwMC92Mi4wIiwgImlkIjogIjVjNGVlN2MzMTE4NDQyNGM5NDJhMWM1MjgxODU3MmZiIiwgInB1YmxpY1VSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6NTAwMC92Mi4wIn1dLCAiZW5kcG9pbnRzX2xpbmtzIjogW10sICJ0eXBlIjogImlkZW50aXR5IiwgIm5hbWUiOiAia2V5c3RvbmUifV0sICJ1c2VyIjogeyJ1c2VybmFtZSI6ICJhZG1pbiIsICJyb2xlc19saW5rcyI6IFtdLCAiaWQiOiAiOTFkNzMyYjY1ODMxNDkxZDhiZDk1MmIzMTExZTYyZGQiLCAicm9sZXMiOiBbeyJuYW1lIjogImhlYXRfc3RhY2tfb3duZXIifSwgeyJuYW1lIjogIl9tZW1iZXJfIn0sIHsibmFtZSI6ICJhZG1pbiJ9XSwgIm5hbWUiOiAiYWRtaW4ifSwgIm1ldGFkYXRhIjogeyJpc19hZG1pbiI6IDAsICJyb2xlcyI6IFsiZDlmZGVlODI1NjE3NGJlNWE3MmFjZGZmNDNkM2VkZDMiLCAiOWZlMmZmOWVlNDM4NGIxODk0YTkwODc4ZDNlOTJiYWIiLCAiN2E1ZTg5MmFiYTE5NDI3NWI3ZjQxZWM4Njg2ZDUwOGYiXX19fTGCAYEwggF9AgEBMFwwVzELMAkGA1UEBhMCVVMxDjAMBgNVBAgMBVVuc2V0MQ4wDAYDVQQHDAVVbnNldDEOMAwGA1UECgwFVW5zZXQxGDAWBgNVBAMMD3d3dy5leGFtcGxlLmNvbQIBATAHBgUrDgMCGjANBgkqhkiG9w0BAQEFAASCAQBkjJ1obp-dG+uEHilZdGvCQu3cmPsI5Atz78lO+iEJea6C5-OQCaLCpdAOd3rbZqn75OKWjbs9GVbXigkpLSKrRyd9U5jJOcxXP6iWIpVr3XE6YjGMlGbfP6W8pBmmc1IvSAgFfie9FUgsBeMDk-wSbggPKsmugKWAkf8e71s6ZQQ5LN65Y6+Orkst03Fojr96XCfpaOPOh19k5FgvKOCFUPKVKpqTio-1W14--wcnrmDU+tOqLDpICQm0QSAOHrX59JVHB0YGy9aCSDocG3pzumxZU1YorDqJCgiUZyAamw9iwzEHVveIko0dIUwy5iipejq+bkmyjb+FyOjZqfCH
                    X-Domain-Id: None
                    X-Domain-Name: None
                    X-Identity-Status: Confirmed
                    X-Project-Domain-Id: default
                    X-Project-Domain-Name: Default
                    X-Project-Id: 4537aca4a4a4462fa4c59ad5b5581f00
                    X-Project-Name: admin
                    X-Role: heat_stack_owner,_member_,admin
                    X-Roles: heat_stack_owner,_member_,admin
                    X-Service-Catalog: [{"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:8774/v2/4537aca4a4a4462fa4c59ad5b5581f00", "region": "RegionOne", "publicURL": "http://172.21.7.40:8774/v2/4537aca4a4a4462fa4c59ad5b5581f00", "internalURL": "http://172.21.7.40:8774/v2/4537aca4a4a4462fa4c59ad5b5581f00", "id": "16b15cc5ff504cb89f58664e27a69c69"}], "type": "compute", "name": "nova"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:9696/", "region": "RegionOne", "publicURL": "http://172.21.7.40:9696/", "internalURL": "http://172.21.7.40:9696/", "id": "1b293a81696b4b7f896ead4622a1c2a1"}], "type": "network", "name": "neutron"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:8776/v2/4537aca4a4a4462fa4c59ad5b5581f00", "region": "RegionOne", "publicURL": "http://172.21.7.40:8776/v2/4537aca4a4a4462fa4c59ad5b5581f00", "internalURL": "http://172.21.7.40:8776/v2/4537aca4a4a4462fa4c59ad5b5581f00", "id": "3a7679cce7df4acfa16b3ca52ddcfc82"}], "type": "volumev2", "name": "cinderv2"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:8774/v3", "region": "RegionOne", "publicURL": "http://172.21.7.40:8774/v3", "internalURL": "http://172.21.7.40:8774/v3", "id": "0bb1d1b88afe40da93bcb1584ca17fb9"}], "type": "computev3", "name": "novav3"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:8080", "region": "RegionOne", "publicURL": "http://172.21.7.40:8080", "internalURL": "http://172.21.7.40:8080", "id": "1e32e172e79c4c5aa6b5c7f8d75af4fb"}], "type": "s3", "name": "swift_s3"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:9292", "region": "RegionOne", "publicURL": "http://172.21.7.40:9292", "internalURL": "http://172.21.7.40:9292", "id": "3d1c792651a049c5a61e35bfefc4c88b"}], "type": "image", "name": "glance"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:8777", "region": "RegionOne", "publicURL": "http://172.21.7.40:8777", "internalURL": "http://172.21.7.40:8777", "id": "39a4c06423a8493c928da18f4a5ccc1f"}], "type": "metering", "name": "ceilometer"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:8000/v1/", "region": "RegionOne", "publicURL": "http://172.21.7.40:8000/v1/", "internalURL": "http://172.21.7.40:8000/v1/", "id": "5570b8f811494e1b955db6e503df2afd"}], "type": "cloudformation", "name": "heat-cfn"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:8776/v1/4537aca4a4a4462fa4c59ad5b5581f00", "region": "RegionOne", "publicURL": "http://172.21.7.40:8776/v1/4537aca4a4a4462fa4c59ad5b5581f00", "internalURL": "http://172.21.7.40:8776/v1/4537aca4a4a4462fa4c59ad5b5581f00", "id": "0a1c8da4f156495aad2130e2c0691982"}], "type": "volume", "name": "cinder"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:8773/services/Admin", "region": "RegionOne", "publicURL": "http://172.21.7.40:8773/services/Cloud", "internalURL": "http://172.21.7.40:8773/services/Cloud", "id": "033f67e9500c49ca8f8b1893e2a7edaf"}], "type": "ec2", "name": "nova_ec2"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:8004/v1/4537aca4a4a4462fa4c59ad5b5581f00", "region": "RegionOne", "publicURL": "http://172.21.7.40:8004/v1/4537aca4a4a4462fa4c59ad5b5581f00", "internalURL": "http://172.21.7.40:8004/v1/4537aca4a4a4462fa4c59ad5b5581f00", "id": "4beb644253ae477f9e9496eedd1093a5"}], "type": "orchestration", "name": "heat"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:8080/", "region": "RegionOne", "publicURL": "http://172.21.7.40:8080/v1/AUTH_4537aca4a4a4462fa4c59ad5b5581f00", "internalURL": "http://172.21.7.40:8080/v1/AUTH_4537aca4a4a4462fa4c59ad5b5581f00", "id": "3a106354261043299a5d247e5f2594d2"}], "type": "object-store", "name": "swift"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:35357/v2.0", "region": "RegionOne", "publicURL": "http://172.21.7.40:5000/v2.0", "internalURL": "http://172.21.7.40:5000/v2.0", "id": "5c4ee7c31184424c942a1c52818572fb"}], "type": "identity", "name": "keystone"}]
                    X-Tenant: admin
                    X-Tenant-Id: 4537aca4a4a4462fa4c59ad5b5581f00
                    X-Tenant-Name: admin
                    X-User: admin
                    X-User-Domain-Id: default
                    X-User-Domain-Name: Default
                    X-User-Id: 91d732b65831491d8bd952b3111e62dd
                    X-User-Name: admin
                    
                    action_result = {
                    'servers': [
                               {
                                'status': 'SHUTOFF', 
                                'updated': '2015-03-16T01:14:52Z', 
                                'hostId': 'c05e5a688f7d65f63ae1885709c830eca9d3c76ec90f46f3d98fd07e', 
                                'addresses': {}, 
                                'links': [
                                         {'href': u'http://172.21.7.40:8774/v2/4537aca4a4a4462fa4c59ad5b5581f00/servers/eae21d5d-61d6-4aa2-a284-a1d3495c1299', 'rel': 'self'}, 
                                         {'href': u'http://172.21.7.40:8774/4537aca4a4a4462fa4c59ad5b5581f00/servers/eae21d5d-61d6-4aa2-a284-a1d3495c1299', 'rel': 'bookmark'}
                                         ], 
                                'image': {
                                          'id': '3af21b70-25cd-47b4-8874-b1e597be7e07', 
                                          'links': [
                                                   {'href': u'http://172.21.7.40:8774/4537aca4a4a4462fa4c59ad5b5581f00/images/3af21b70-25cd-47b4-8874-b1e597be7e07', 'rel': 'bookmark'}
                                                   ]
                                         }, 
                                'flavor': {
                                           'id': '1', 
                                           'links': [
                                                    {'href': u'http://172.21.7.40:8774/4537aca4a4a4462fa4c59ad5b5581f00/flavors/1', 'rel': 'bookmark'}
                                                    ]
                                          }, 
                                'id': 'eae21d5d-61d6-4aa2-a284-a1d3495c1299', 
                                'user_id': u'91d732b65831491d8bd952b3111e62dd', 
                                'name': u'test0', 
                                'created': '2015-03-10T03:04:45Z', 
                                'tenant_id': u'4537aca4a4a4462fa4c59ad5b5581f00', 
                                'accessIPv4': '', 
                                'accessIPv6': '', 
                                'metadata': {}
                               }
                              ]
                    }
                    ======================================================================================
                    """
            except Fault as ex:
                response = ex

        if not response:
            # No exceptions; convert action_result into a
            # ResponseObject
            resp_obj = None
            if type(action_result) is dict or action_result is None:
                resp_obj = ResponseObject(action_result)
            elif isinstance(action_result, ResponseObject):
                resp_obj = action_result
            else:
                response = action_result

            # Run post-processing extensions
            if resp_obj:
                # Do a preserialize to set up the response object
                serializers = getattr(meth, 'wsgi_serializers', {})
                resp_obj._bind_method_serializers(serializers)
                if hasattr(meth, 'wsgi_code'):
                    resp_obj._default_code = meth.wsgi_code
                resp_obj.preserialize(accept, self.default_serializers)

                # Process post-processing extensions
                response = self.post_process_extensions(post, resp_obj,
                                                        request, action_args)

            if resp_obj and not response:
                response = resp_obj.serialize(request, accept,
                                              self.default_serializers)

        if hasattr(response, 'headers'):
            if context:
                response.headers.add('x-compute-request-id',
                                     context.request_id)

            for hdr, val in response.headers.items():
                # Headers must be utf-8 strings
                response.headers[hdr] = utils.utf8(str(val))

        """
        ======================================================================================
        response = 200 OK
        Content-Type: application/json
        Content-Length: 1520
        x-compute-request-id: req-712c9eb8-55e4-415a-ba36-436ef8f17e87
        
        {"servers": [{"status": "SHUTOFF", "updated": "2015-03-17T16:59:39Z", "hostId": "80edf4278faf2e792eedcf39ba7cda12df2169bdaad7ea118081e07f", "OS-EXT-SRV-ATTR:host": "node02.shinian.com", "addresses": {}, "links": [{"href": "http://172.21.6.180:8774/v2/2a3cc2062e154e148b50e79ed3736e4a/servers/770ae6a2-f7dc-4f90-af0e-361bb22ce9cc", "rel": "self"}, {"href": "http://172.21.6.180:8774/2a3cc2062e154e148b50e79ed3736e4a/servers/770ae6a2-f7dc-4f90-af0e-361bb22ce9cc", "rel": "bookmark"}], "key_name": "oskey", "image": {"id": "d407bd3e-aa1c-49ea-bc84-00584182b283", "links": [{"href": "http://172.21.6.180:8774/2a3cc2062e154e148b50e79ed3736e4a/images/d407bd3e-aa1c-49ea-bc84-00584182b283", "rel": "bookmark"}]}, "OS-EXT-STS:task_state": null, "OS-EXT-STS:vm_state": "stopped", "OS-EXT-SRV-ATTR:instance_name": "instance-00000002", "OS-SRV-USG:launched_at": "2015-03-17T15:25:31.000000", "OS-EXT-SRV-ATTR:hypervisor_hostname": "node02.shinian.com", "flavor": {"id": "1", "links": [{"href": "http://172.21.6.180:8774/2a3cc2062e154e148b50e79ed3736e4a/flavors/1", "rel": "bookmark"}]}, "id": "770ae6a2-f7dc-4f90-af0e-361bb22ce9cc", "OS-SRV-USG:terminated_at": null, "OS-EXT-AZ:availability_zone": "nova", "user_id": "c01f7e46dfe84393bc214626edebc959", "name": "test0", "created": "2015-03-17T15:24:46Z", "tenant_id": "2a3cc2062e154e148b50e79ed3736e4a", "OS-DCF:diskConfig": "MANUAL", "os-extended-volumes:volumes_attached": [], "accessIPv4": "", "accessIPv6": "", "OS-EXT-STS:power_state": 4, "config_drive": "", "metadata": {}}]}
        ======================================================================================
        """
        return response

    def get_method(self, request, action, content_type, body):
        """
        ======================================================================================
        request = GET /v2/4537aca4a4a4462fa4c59ad5b5581f00/servers/detail HTTP/1.0
        Accept: application/json
        Accept-Encoding: gzip, deflate, compress
        Content-Length: 0
        Content-Type: text/plain
        Host: 172.21.7.40:8774
        User-Agent: python-novaclient
        X-Auth-Project-Id: admin
        X-Auth-Token: MIIT9wYJKoZIhvcNAQcCoIIT6DCCE+QCAQExCTAHBgUrDgMCGjCCEk0GCSqGSIb3DQEHAaCCEj4EghI6eyJhY2Nlc3MiOiB7InRva2VuIjogeyJpc3N1ZWRfYXQiOiAiMjAxNS0wMy0xNlQwMzozNjoyNS43OTc5MjAiLCAiZXhwaXJlcyI6ICIyMDE1LTAzLTE2VDA0OjM2OjI1WiIsICJpZCI6ICJwbGFjZWhvbGRlciIsICJ0ZW5hbnQiOiB7ImRlc2NyaXB0aW9uIjogImFkbWluIHRlbmFudCIsICJlbmFibGVkIjogdHJ1ZSwgImlkIjogIjQ1MzdhY2E0YTRhNDQ2MmZhNGM1OWFkNWI1NTgxZjAwIiwgIm5hbWUiOiAiYWRtaW4ifX0sICJzZXJ2aWNlQ2F0YWxvZyI6IFt7ImVuZHBvaW50cyI6IFt7ImFkbWluVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo4Nzc0L3YyLzQ1MzdhY2E0YTRhNDQ2MmZhNGM1OWFkNWI1NTgxZjAwIiwgInJlZ2lvbiI6ICJSZWdpb25PbmUiLCAiaW50ZXJuYWxVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjg3NzQvdjIvNDUzN2FjYTRhNGE0NDYyZmE0YzU5YWQ1YjU1ODFmMDAiLCAiaWQiOiAiMTZiMTVjYzVmZjUwNGNiODlmNTg2NjRlMjdhNjljNjkiLCAicHVibGljVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo4Nzc0L3YyLzQ1MzdhY2E0YTRhNDQ2MmZhNGM1OWFkNWI1NTgxZjAwIn1dLCAiZW5kcG9pbnRzX2xpbmtzIjogW10sICJ0eXBlIjogImNvbXB1dGUiLCAibmFtZSI6ICJub3ZhIn0sIHsiZW5kcG9pbnRzIjogW3siYWRtaW5VUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjk2OTYvIiwgInJlZ2lvbiI6ICJSZWdpb25PbmUiLCAiaW50ZXJuYWxVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjk2OTYvIiwgImlkIjogIjFiMjkzYTgxNjk2YjRiN2Y4OTZlYWQ0NjIyYTFjMmExIiwgInB1YmxpY1VSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6OTY5Ni8ifV0sICJlbmRwb2ludHNfbGlua3MiOiBbXSwgInR5cGUiOiAibmV0d29yayIsICJuYW1lIjogIm5ldXRyb24ifSwgeyJlbmRwb2ludHMiOiBbeyJhZG1pblVSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODc3Ni92Mi80NTM3YWNhNGE0YTQ0NjJmYTRjNTlhZDViNTU4MWYwMCIsICJyZWdpb24iOiAiUmVnaW9uT25lIiwgImludGVybmFsVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo4Nzc2L3YyLzQ1MzdhY2E0YTRhNDQ2MmZhNGM1OWFkNWI1NTgxZjAwIiwgImlkIjogIjNhNzY3OWNjZTdkZjRhY2ZhMTZiM2NhNTJkZGNmYzgyIiwgInB1YmxpY1VSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODc3Ni92Mi80NTM3YWNhNGE0YTQ0NjJmYTRjNTlhZDViNTU4MWYwMCJ9XSwgImVuZHBvaW50c19saW5rcyI6IFtdLCAidHlwZSI6ICJ2b2x1bWV2MiIsICJuYW1lIjogImNpbmRlcnYyIn0sIHsiZW5kcG9pbnRzIjogW3siYWRtaW5VUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjg3NzQvdjMiLCAicmVnaW9uIjogIlJlZ2lvbk9uZSIsICJpbnRlcm5hbFVSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODc3NC92MyIsICJpZCI6ICIwYmIxZDFiODhhZmU0MGRhOTNiY2IxNTg0Y2ExN2ZiOSIsICJwdWJsaWNVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjg3NzQvdjMifV0sICJlbmRwb2ludHNfbGlua3MiOiBbXSwgInR5cGUiOiAiY29tcHV0ZXYzIiwgIm5hbWUiOiAibm92YXYzIn0sIHsiZW5kcG9pbnRzIjogW3siYWRtaW5VUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjgwODAiLCAicmVnaW9uIjogIlJlZ2lvbk9uZSIsICJpbnRlcm5hbFVSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODA4MCIsICJpZCI6ICIxZTMyZTE3MmU3OWM0YzVhYTZiNWM3ZjhkNzVhZjRmYiIsICJwdWJsaWNVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjgwODAifV0sICJlbmRwb2ludHNfbGlua3MiOiBbXSwgInR5cGUiOiAiczMiLCAibmFtZSI6ICJzd2lmdF9zMyJ9LCB7ImVuZHBvaW50cyI6IFt7ImFkbWluVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo5MjkyIiwgInJlZ2lvbiI6ICJSZWdpb25PbmUiLCAiaW50ZXJuYWxVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjkyOTIiLCAiaWQiOiAiM2QxYzc5MjY1MWEwNDljNWE2MWUzNWJmZWZjNGM4OGIiLCAicHVibGljVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo5MjkyIn1dLCAiZW5kcG9pbnRzX2xpbmtzIjogW10sICJ0eXBlIjogImltYWdlIiwgIm5hbWUiOiAiZ2xhbmNlIn0sIHsiZW5kcG9pbnRzIjogW3siYWRtaW5VUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjg3NzciLCAicmVnaW9uIjogIlJlZ2lvbk9uZSIsICJpbnRlcm5hbFVSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODc3NyIsICJpZCI6ICIzOWE0YzA2NDIzYTg0OTNjOTI4ZGExOGY0YTVjY2MxZiIsICJwdWJsaWNVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjg3NzcifV0sICJlbmRwb2ludHNfbGlua3MiOiBbXSwgInR5cGUiOiAibWV0ZXJpbmciLCAibmFtZSI6ICJjZWlsb21ldGVyIn0sIHsiZW5kcG9pbnRzIjogW3siYWRtaW5VUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjgwMDAvdjEvIiwgInJlZ2lvbiI6ICJSZWdpb25PbmUiLCAiaW50ZXJuYWxVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjgwMDAvdjEvIiwgImlkIjogIjU1NzBiOGY4MTE0OTRlMWI5NTVkYjZlNTAzZGYyYWZkIiwgInB1YmxpY1VSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODAwMC92MS8ifV0sICJlbmRwb2ludHNfbGlua3MiOiBbXSwgInR5cGUiOiAiY2xvdWRmb3JtYXRpb24iLCAibmFtZSI6ICJoZWF0LWNmbiJ9LCB7ImVuZHBvaW50cyI6IFt7ImFkbWluVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo4Nzc2L3YxLzQ1MzdhY2E0YTRhNDQ2MmZhNGM1OWFkNWI1NTgxZjAwIiwgInJlZ2lvbiI6ICJSZWdpb25PbmUiLCAiaW50ZXJuYWxVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjg3NzYvdjEvNDUzN2FjYTRhNGE0NDYyZmE0YzU5YWQ1YjU1ODFmMDAiLCAiaWQiOiAiMGExYzhkYTRmMTU2NDk1YWFkMjEzMGUyYzA2OTE5ODIiLCAicHVibGljVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo4Nzc2L3YxLzQ1MzdhY2E0YTRhNDQ2MmZhNGM1OWFkNWI1NTgxZjAwIn1dLCAiZW5kcG9pbnRzX2xpbmtzIjogW10sICJ0eXBlIjogInZvbHVtZSIsICJuYW1lIjogImNpbmRlciJ9LCB7ImVuZHBvaW50cyI6IFt7ImFkbWluVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo4NzczL3NlcnZpY2VzL0FkbWluIiwgInJlZ2lvbiI6ICJSZWdpb25PbmUiLCAiaW50ZXJuYWxVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjg3NzMvc2VydmljZXMvQ2xvdWQiLCAiaWQiOiAiMDMzZjY3ZTk1MDBjNDljYThmOGIxODkzZTJhN2VkYWYiLCAicHVibGljVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo4NzczL3NlcnZpY2VzL0Nsb3VkIn1dLCAiZW5kcG9pbnRzX2xpbmtzIjogW10sICJ0eXBlIjogImVjMiIsICJuYW1lIjogIm5vdmFfZWMyIn0sIHsiZW5kcG9pbnRzIjogW3siYWRtaW5VUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjgwMDQvdjEvNDUzN2FjYTRhNGE0NDYyZmE0YzU5YWQ1YjU1ODFmMDAiLCAicmVnaW9uIjogIlJlZ2lvbk9uZSIsICJpbnRlcm5hbFVSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODAwNC92MS80NTM3YWNhNGE0YTQ0NjJmYTRjNTlhZDViNTU4MWYwMCIsICJpZCI6ICI0YmViNjQ0MjUzYWU0NzdmOWU5NDk2ZWVkZDEwOTNhNSIsICJwdWJsaWNVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjgwMDQvdjEvNDUzN2FjYTRhNGE0NDYyZmE0YzU5YWQ1YjU1ODFmMDAifV0sICJlbmRwb2ludHNfbGlua3MiOiBbXSwgInR5cGUiOiAib3JjaGVzdHJhdGlvbiIsICJuYW1lIjogImhlYXQifSwgeyJlbmRwb2ludHMiOiBbeyJhZG1pblVSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODA4MC8iLCAicmVnaW9uIjogIlJlZ2lvbk9uZSIsICJpbnRlcm5hbFVSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODA4MC92MS9BVVRIXzQ1MzdhY2E0YTRhNDQ2MmZhNGM1OWFkNWI1NTgxZjAwIiwgImlkIjogIjNhMTA2MzU0MjYxMDQzMjk5YTVkMjQ3ZTVmMjU5NGQyIiwgInB1YmxpY1VSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODA4MC92MS9BVVRIXzQ1MzdhY2E0YTRhNDQ2MmZhNGM1OWFkNWI1NTgxZjAwIn1dLCAiZW5kcG9pbnRzX2xpbmtzIjogW10sICJ0eXBlIjogIm9iamVjdC1zdG9yZSIsICJuYW1lIjogInN3aWZ0In0sIHsiZW5kcG9pbnRzIjogW3siYWRtaW5VUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjM1MzU3L3YyLjAiLCAicmVnaW9uIjogIlJlZ2lvbk9uZSIsICJpbnRlcm5hbFVSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6NTAwMC92Mi4wIiwgImlkIjogIjVjNGVlN2MzMTE4NDQyNGM5NDJhMWM1MjgxODU3MmZiIiwgInB1YmxpY1VSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6NTAwMC92Mi4wIn1dLCAiZW5kcG9pbnRzX2xpbmtzIjogW10sICJ0eXBlIjogImlkZW50aXR5IiwgIm5hbWUiOiAia2V5c3RvbmUifV0sICJ1c2VyIjogeyJ1c2VybmFtZSI6ICJhZG1pbiIsICJyb2xlc19saW5rcyI6IFtdLCAiaWQiOiAiOTFkNzMyYjY1ODMxNDkxZDhiZDk1MmIzMTExZTYyZGQiLCAicm9sZXMiOiBbeyJuYW1lIjogImhlYXRfc3RhY2tfb3duZXIifSwgeyJuYW1lIjogIl9tZW1iZXJfIn0sIHsibmFtZSI6ICJhZG1pbiJ9XSwgIm5hbWUiOiAiYWRtaW4ifSwgIm1ldGFkYXRhIjogeyJpc19hZG1pbiI6IDAsICJyb2xlcyI6IFsiZDlmZGVlODI1NjE3NGJlNWE3MmFjZGZmNDNkM2VkZDMiLCAiOWZlMmZmOWVlNDM4NGIxODk0YTkwODc4ZDNlOTJiYWIiLCAiN2E1ZTg5MmFiYTE5NDI3NWI3ZjQxZWM4Njg2ZDUwOGYiXX19fTGCAYEwggF9AgEBMFwwVzELMAkGA1UEBhMCVVMxDjAMBgNVBAgMBVVuc2V0MQ4wDAYDVQQHDAVVbnNldDEOMAwGA1UECgwFVW5zZXQxGDAWBgNVBAMMD3d3dy5leGFtcGxlLmNvbQIBATAHBgUrDgMCGjANBgkqhkiG9w0BAQEFAASCAQBQf7jWBgs5NTmDg+GrOkg0QwZYl2FIs8QEEq+cUGKHpZw47RuWYTpxth3r7YBWXHuVkj41o3y44r8X+KWqMh0-gRloztQQs5j+OjmnnTevqcU7nMb-mIInEflwr6OfVG0n7bwmb8880637z658op-30jnD-ls129Zwy4jAapXblYsFnPU6i8C-3CCzqdP7kd3F1DZmBVwxntuCFXkNCIiD1d-FZnGgdp1l4ruUfX5JffWAkaP77LfmVz3McsxSXLF4n13dF+B7O29bAz+s+TOvS+QtPjh57kyZoR9fPAIDQNomZYOJd0M9b0XMDNFoi60p47rzeUoZyTkZKsROSI9W
        X-Domain-Id: None
        X-Domain-Name: None
        X-Identity-Status: Confirmed
        X-Project-Domain-Id: default
        X-Project-Domain-Name: Default
        X-Project-Id: 4537aca4a4a4462fa4c59ad5b5581f00
        X-Project-Name: admin
        X-Role: heat_stack_owner,_member_,admin
        X-Roles: heat_stack_owner,_member_,admin
        X-Service-Catalog: [{"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:8774/v2/4537aca4a4a4462fa4c59ad5b5581f00", "region": "RegionOne", "publicURL": "http://172.21.7.40:8774/v2/4537aca4a4a4462fa4c59ad5b5581f00", "internalURL": "http://172.21.7.40:8774/v2/4537aca4a4a4462fa4c59ad5b5581f00", "id": "16b15cc5ff504cb89f58664e27a69c69"}], "type": "compute", "name": "nova"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:9696/", "region": "RegionOne", "publicURL": "http://172.21.7.40:9696/", "internalURL": "http://172.21.7.40:9696/", "id": "1b293a81696b4b7f896ead4622a1c2a1"}], "type": "network", "name": "neutron"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:8776/v2/4537aca4a4a4462fa4c59ad5b5581f00", "region": "RegionOne", "publicURL": "http://172.21.7.40:8776/v2/4537aca4a4a4462fa4c59ad5b5581f00", "internalURL": "http://172.21.7.40:8776/v2/4537aca4a4a4462fa4c59ad5b5581f00", "id": "3a7679cce7df4acfa16b3ca52ddcfc82"}], "type": "volumev2", "name": "cinderv2"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:8774/v3", "region": "RegionOne", "publicURL": "http://172.21.7.40:8774/v3", "internalURL": "http://172.21.7.40:8774/v3", "id": "0bb1d1b88afe40da93bcb1584ca17fb9"}], "type": "computev3", "name": "novav3"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:8080", "region": "RegionOne", "publicURL": "http://172.21.7.40:8080", "internalURL": "http://172.21.7.40:8080", "id": "1e32e172e79c4c5aa6b5c7f8d75af4fb"}], "type": "s3", "name": "swift_s3"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:9292", "region": "RegionOne", "publicURL": "http://172.21.7.40:9292", "internalURL": "http://172.21.7.40:9292", "id": "3d1c792651a049c5a61e35bfefc4c88b"}], "type": "image", "name": "glance"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:8777", "region": "RegionOne", "publicURL": "http://172.21.7.40:8777", "internalURL": "http://172.21.7.40:8777", "id": "39a4c06423a8493c928da18f4a5ccc1f"}], "type": "metering", "name": "ceilometer"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:8000/v1/", "region": "RegionOne", "publicURL": "http://172.21.7.40:8000/v1/", "internalURL": "http://172.21.7.40:8000/v1/", "id": "5570b8f811494e1b955db6e503df2afd"}], "type": "cloudformation", "name": "heat-cfn"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:8776/v1/4537aca4a4a4462fa4c59ad5b5581f00", "region": "RegionOne", "publicURL": "http://172.21.7.40:8776/v1/4537aca4a4a4462fa4c59ad5b5581f00", "internalURL": "http://172.21.7.40:8776/v1/4537aca4a4a4462fa4c59ad5b5581f00", "id": "0a1c8da4f156495aad2130e2c0691982"}], "type": "volume", "name": "cinder"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:8773/services/Admin", "region": "RegionOne", "publicURL": "http://172.21.7.40:8773/services/Cloud", "internalURL": "http://172.21.7.40:8773/services/Cloud", "id": "033f67e9500c49ca8f8b1893e2a7edaf"}], "type": "ec2", "name": "nova_ec2"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:8004/v1/4537aca4a4a4462fa4c59ad5b5581f00", "region": "RegionOne", "publicURL": "http://172.21.7.40:8004/v1/4537aca4a4a4462fa4c59ad5b5581f00", "internalURL": "http://172.21.7.40:8004/v1/4537aca4a4a4462fa4c59ad5b5581f00", "id": "4beb644253ae477f9e9496eedd1093a5"}], "type": "orchestration", "name": "heat"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:8080/", "region": "RegionOne", "publicURL": "http://172.21.7.40:8080/v1/AUTH_4537aca4a4a4462fa4c59ad5b5581f00", "internalURL": "http://172.21.7.40:8080/v1/AUTH_4537aca4a4a4462fa4c59ad5b5581f00", "id": "3a106354261043299a5d247e5f2594d2"}], "type": "object-store", "name": "swift"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:35357/v2.0", "region": "RegionOne", "publicURL": "http://172.21.7.40:5000/v2.0", "internalURL": "http://172.21.7.40:5000/v2.0", "id": "5c4ee7c31184424c942a1c52818572fb"}], "type": "identity", "name": "keystone"}]
        X-Tenant: admin
        X-Tenant-Id: 4537aca4a4a4462fa4c59ad5b5581f00
        X-Tenant-Name: admin
        X-User: admin
        X-User-Domain-Id: default
        X-User-Domain-Name: Default
        X-User-Id: 91d732b65831491d8bd952b3111e62dd
        X-User-Name: admin
        
        action = detail
        content_type = None
        body = 
        ======================================================================================
        """
        """
        如果action不等于'action'，则：
        meth = action
        meth_extensions = self.wsgi_extensions.get(action, [])
        即从@wsgi.extends修饰的没有action参数的扩展方法中选取，作为meth对应的扩展方法；
        
        如果action等于'action'，则：
        meth = self.wsgi_actions[action_name]
        即从@wsgi.actions修饰的扩展方法中选取，作为meth方法；
        meth_extensions = self.wsgi_action_extensions.get(action_name, [])
        即从@wsgi.extends修饰的有action参数的扩展方法中选取，作为meth对应的扩展方法；
        """
        
        """
        如果action不等于'action'，则：
        meth = action
        meth_extensions = self.wsgi_extensions.get(action, [])
        即从@wsgi.extends修饰的没有action参数的扩展方法中选取，作为meth对应的扩展方法；
        
        如果action等于'action'，则：
        meth = self.wsgi_actions[action_name]
        即从@wsgi.actions修饰的扩展方法中选取，作为meth方法；
        meth_extensions = self.wsgi_action_extensions.get(action_name, [])
        即从@wsgi.extends修饰的有action参数的扩展方法中选取，作为meth对应的扩展方法；
        """
        meth, extensions = self._get_method(request,
                                            action,
                                            content_type,
                                            body)
        if self.inherits:
            _meth, parent_ext = self.inherits.get_method(request,
                                                         action,
                                                         content_type,
                                                         body)
            extensions.extend(parent_ext)
        return meth, extensions

    def _get_method(self, request, action, content_type, body):
        """
        Look up the action-specific method and its extensions.
        """
        """
        ======================================================================================
        request = GET /v2/4537aca4a4a4462fa4c59ad5b5581f00/servers/detail HTTP/1.0
        Accept: application/json
        Accept-Encoding: gzip, deflate, compress
        Content-Length: 0
        Content-Type: text/plain
        Host: 172.21.7.40:8774
        User-Agent: python-novaclient
        X-Auth-Project-Id: admin
        X-Auth-Token: MIIT9wYJKoZIhvcNAQcCoIIT6DCCE+QCAQExCTAHBgUrDgMCGjCCEk0GCSqGSIb3DQEHAaCCEj4EghI6eyJhY2Nlc3MiOiB7InRva2VuIjogeyJpc3N1ZWRfYXQiOiAiMjAxNS0wMy0xNlQwMzozNjoyNS43OTc5MjAiLCAiZXhwaXJlcyI6ICIyMDE1LTAzLTE2VDA0OjM2OjI1WiIsICJpZCI6ICJwbGFjZWhvbGRlciIsICJ0ZW5hbnQiOiB7ImRlc2NyaXB0aW9uIjogImFkbWluIHRlbmFudCIsICJlbmFibGVkIjogdHJ1ZSwgImlkIjogIjQ1MzdhY2E0YTRhNDQ2MmZhNGM1OWFkNWI1NTgxZjAwIiwgIm5hbWUiOiAiYWRtaW4ifX0sICJzZXJ2aWNlQ2F0YWxvZyI6IFt7ImVuZHBvaW50cyI6IFt7ImFkbWluVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo4Nzc0L3YyLzQ1MzdhY2E0YTRhNDQ2MmZhNGM1OWFkNWI1NTgxZjAwIiwgInJlZ2lvbiI6ICJSZWdpb25PbmUiLCAiaW50ZXJuYWxVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjg3NzQvdjIvNDUzN2FjYTRhNGE0NDYyZmE0YzU5YWQ1YjU1ODFmMDAiLCAiaWQiOiAiMTZiMTVjYzVmZjUwNGNiODlmNTg2NjRlMjdhNjljNjkiLCAicHVibGljVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo4Nzc0L3YyLzQ1MzdhY2E0YTRhNDQ2MmZhNGM1OWFkNWI1NTgxZjAwIn1dLCAiZW5kcG9pbnRzX2xpbmtzIjogW10sICJ0eXBlIjogImNvbXB1dGUiLCAibmFtZSI6ICJub3ZhIn0sIHsiZW5kcG9pbnRzIjogW3siYWRtaW5VUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjk2OTYvIiwgInJlZ2lvbiI6ICJSZWdpb25PbmUiLCAiaW50ZXJuYWxVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjk2OTYvIiwgImlkIjogIjFiMjkzYTgxNjk2YjRiN2Y4OTZlYWQ0NjIyYTFjMmExIiwgInB1YmxpY1VSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6OTY5Ni8ifV0sICJlbmRwb2ludHNfbGlua3MiOiBbXSwgInR5cGUiOiAibmV0d29yayIsICJuYW1lIjogIm5ldXRyb24ifSwgeyJlbmRwb2ludHMiOiBbeyJhZG1pblVSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODc3Ni92Mi80NTM3YWNhNGE0YTQ0NjJmYTRjNTlhZDViNTU4MWYwMCIsICJyZWdpb24iOiAiUmVnaW9uT25lIiwgImludGVybmFsVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo4Nzc2L3YyLzQ1MzdhY2E0YTRhNDQ2MmZhNGM1OWFkNWI1NTgxZjAwIiwgImlkIjogIjNhNzY3OWNjZTdkZjRhY2ZhMTZiM2NhNTJkZGNmYzgyIiwgInB1YmxpY1VSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODc3Ni92Mi80NTM3YWNhNGE0YTQ0NjJmYTRjNTlhZDViNTU4MWYwMCJ9XSwgImVuZHBvaW50c19saW5rcyI6IFtdLCAidHlwZSI6ICJ2b2x1bWV2MiIsICJuYW1lIjogImNpbmRlcnYyIn0sIHsiZW5kcG9pbnRzIjogW3siYWRtaW5VUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjg3NzQvdjMiLCAicmVnaW9uIjogIlJlZ2lvbk9uZSIsICJpbnRlcm5hbFVSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODc3NC92MyIsICJpZCI6ICIwYmIxZDFiODhhZmU0MGRhOTNiY2IxNTg0Y2ExN2ZiOSIsICJwdWJsaWNVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjg3NzQvdjMifV0sICJlbmRwb2ludHNfbGlua3MiOiBbXSwgInR5cGUiOiAiY29tcHV0ZXYzIiwgIm5hbWUiOiAibm92YXYzIn0sIHsiZW5kcG9pbnRzIjogW3siYWRtaW5VUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjgwODAiLCAicmVnaW9uIjogIlJlZ2lvbk9uZSIsICJpbnRlcm5hbFVSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODA4MCIsICJpZCI6ICIxZTMyZTE3MmU3OWM0YzVhYTZiNWM3ZjhkNzVhZjRmYiIsICJwdWJsaWNVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjgwODAifV0sICJlbmRwb2ludHNfbGlua3MiOiBbXSwgInR5cGUiOiAiczMiLCAibmFtZSI6ICJzd2lmdF9zMyJ9LCB7ImVuZHBvaW50cyI6IFt7ImFkbWluVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo5MjkyIiwgInJlZ2lvbiI6ICJSZWdpb25PbmUiLCAiaW50ZXJuYWxVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjkyOTIiLCAiaWQiOiAiM2QxYzc5MjY1MWEwNDljNWE2MWUzNWJmZWZjNGM4OGIiLCAicHVibGljVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo5MjkyIn1dLCAiZW5kcG9pbnRzX2xpbmtzIjogW10sICJ0eXBlIjogImltYWdlIiwgIm5hbWUiOiAiZ2xhbmNlIn0sIHsiZW5kcG9pbnRzIjogW3siYWRtaW5VUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjg3NzciLCAicmVnaW9uIjogIlJlZ2lvbk9uZSIsICJpbnRlcm5hbFVSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODc3NyIsICJpZCI6ICIzOWE0YzA2NDIzYTg0OTNjOTI4ZGExOGY0YTVjY2MxZiIsICJwdWJsaWNVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjg3NzcifV0sICJlbmRwb2ludHNfbGlua3MiOiBbXSwgInR5cGUiOiAibWV0ZXJpbmciLCAibmFtZSI6ICJjZWlsb21ldGVyIn0sIHsiZW5kcG9pbnRzIjogW3siYWRtaW5VUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjgwMDAvdjEvIiwgInJlZ2lvbiI6ICJSZWdpb25PbmUiLCAiaW50ZXJuYWxVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjgwMDAvdjEvIiwgImlkIjogIjU1NzBiOGY4MTE0OTRlMWI5NTVkYjZlNTAzZGYyYWZkIiwgInB1YmxpY1VSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODAwMC92MS8ifV0sICJlbmRwb2ludHNfbGlua3MiOiBbXSwgInR5cGUiOiAiY2xvdWRmb3JtYXRpb24iLCAibmFtZSI6ICJoZWF0LWNmbiJ9LCB7ImVuZHBvaW50cyI6IFt7ImFkbWluVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo4Nzc2L3YxLzQ1MzdhY2E0YTRhNDQ2MmZhNGM1OWFkNWI1NTgxZjAwIiwgInJlZ2lvbiI6ICJSZWdpb25PbmUiLCAiaW50ZXJuYWxVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjg3NzYvdjEvNDUzN2FjYTRhNGE0NDYyZmE0YzU5YWQ1YjU1ODFmMDAiLCAiaWQiOiAiMGExYzhkYTRmMTU2NDk1YWFkMjEzMGUyYzA2OTE5ODIiLCAicHVibGljVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo4Nzc2L3YxLzQ1MzdhY2E0YTRhNDQ2MmZhNGM1OWFkNWI1NTgxZjAwIn1dLCAiZW5kcG9pbnRzX2xpbmtzIjogW10sICJ0eXBlIjogInZvbHVtZSIsICJuYW1lIjogImNpbmRlciJ9LCB7ImVuZHBvaW50cyI6IFt7ImFkbWluVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo4NzczL3NlcnZpY2VzL0FkbWluIiwgInJlZ2lvbiI6ICJSZWdpb25PbmUiLCAiaW50ZXJuYWxVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjg3NzMvc2VydmljZXMvQ2xvdWQiLCAiaWQiOiAiMDMzZjY3ZTk1MDBjNDljYThmOGIxODkzZTJhN2VkYWYiLCAicHVibGljVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo4NzczL3NlcnZpY2VzL0Nsb3VkIn1dLCAiZW5kcG9pbnRzX2xpbmtzIjogW10sICJ0eXBlIjogImVjMiIsICJuYW1lIjogIm5vdmFfZWMyIn0sIHsiZW5kcG9pbnRzIjogW3siYWRtaW5VUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjgwMDQvdjEvNDUzN2FjYTRhNGE0NDYyZmE0YzU5YWQ1YjU1ODFmMDAiLCAicmVnaW9uIjogIlJlZ2lvbk9uZSIsICJpbnRlcm5hbFVSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODAwNC92MS80NTM3YWNhNGE0YTQ0NjJmYTRjNTlhZDViNTU4MWYwMCIsICJpZCI6ICI0YmViNjQ0MjUzYWU0NzdmOWU5NDk2ZWVkZDEwOTNhNSIsICJwdWJsaWNVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjgwMDQvdjEvNDUzN2FjYTRhNGE0NDYyZmE0YzU5YWQ1YjU1ODFmMDAifV0sICJlbmRwb2ludHNfbGlua3MiOiBbXSwgInR5cGUiOiAib3JjaGVzdHJhdGlvbiIsICJuYW1lIjogImhlYXQifSwgeyJlbmRwb2ludHMiOiBbeyJhZG1pblVSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODA4MC8iLCAicmVnaW9uIjogIlJlZ2lvbk9uZSIsICJpbnRlcm5hbFVSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODA4MC92MS9BVVRIXzQ1MzdhY2E0YTRhNDQ2MmZhNGM1OWFkNWI1NTgxZjAwIiwgImlkIjogIjNhMTA2MzU0MjYxMDQzMjk5YTVkMjQ3ZTVmMjU5NGQyIiwgInB1YmxpY1VSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODA4MC92MS9BVVRIXzQ1MzdhY2E0YTRhNDQ2MmZhNGM1OWFkNWI1NTgxZjAwIn1dLCAiZW5kcG9pbnRzX2xpbmtzIjogW10sICJ0eXBlIjogIm9iamVjdC1zdG9yZSIsICJuYW1lIjogInN3aWZ0In0sIHsiZW5kcG9pbnRzIjogW3siYWRtaW5VUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjM1MzU3L3YyLjAiLCAicmVnaW9uIjogIlJlZ2lvbk9uZSIsICJpbnRlcm5hbFVSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6NTAwMC92Mi4wIiwgImlkIjogIjVjNGVlN2MzMTE4NDQyNGM5NDJhMWM1MjgxODU3MmZiIiwgInB1YmxpY1VSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6NTAwMC92Mi4wIn1dLCAiZW5kcG9pbnRzX2xpbmtzIjogW10sICJ0eXBlIjogImlkZW50aXR5IiwgIm5hbWUiOiAia2V5c3RvbmUifV0sICJ1c2VyIjogeyJ1c2VybmFtZSI6ICJhZG1pbiIsICJyb2xlc19saW5rcyI6IFtdLCAiaWQiOiAiOTFkNzMyYjY1ODMxNDkxZDhiZDk1MmIzMTExZTYyZGQiLCAicm9sZXMiOiBbeyJuYW1lIjogImhlYXRfc3RhY2tfb3duZXIifSwgeyJuYW1lIjogIl9tZW1iZXJfIn0sIHsibmFtZSI6ICJhZG1pbiJ9XSwgIm5hbWUiOiAiYWRtaW4ifSwgIm1ldGFkYXRhIjogeyJpc19hZG1pbiI6IDAsICJyb2xlcyI6IFsiZDlmZGVlODI1NjE3NGJlNWE3MmFjZGZmNDNkM2VkZDMiLCAiOWZlMmZmOWVlNDM4NGIxODk0YTkwODc4ZDNlOTJiYWIiLCAiN2E1ZTg5MmFiYTE5NDI3NWI3ZjQxZWM4Njg2ZDUwOGYiXX19fTGCAYEwggF9AgEBMFwwVzELMAkGA1UEBhMCVVMxDjAMBgNVBAgMBVVuc2V0MQ4wDAYDVQQHDAVVbnNldDEOMAwGA1UECgwFVW5zZXQxGDAWBgNVBAMMD3d3dy5leGFtcGxlLmNvbQIBATAHBgUrDgMCGjANBgkqhkiG9w0BAQEFAASCAQBQf7jWBgs5NTmDg+GrOkg0QwZYl2FIs8QEEq+cUGKHpZw47RuWYTpxth3r7YBWXHuVkj41o3y44r8X+KWqMh0-gRloztQQs5j+OjmnnTevqcU7nMb-mIInEflwr6OfVG0n7bwmb8880637z658op-30jnD-ls129Zwy4jAapXblYsFnPU6i8C-3CCzqdP7kd3F1DZmBVwxntuCFXkNCIiD1d-FZnGgdp1l4ruUfX5JffWAkaP77LfmVz3McsxSXLF4n13dF+B7O29bAz+s+TOvS+QtPjh57kyZoR9fPAIDQNomZYOJd0M9b0XMDNFoi60p47rzeUoZyTkZKsROSI9W
        X-Domain-Id: None
        X-Domain-Name: None
        X-Identity-Status: Confirmed
        X-Project-Domain-Id: default
        X-Project-Domain-Name: Default
        X-Project-Id: 4537aca4a4a4462fa4c59ad5b5581f00
        X-Project-Name: admin
        X-Role: heat_stack_owner,_member_,admin
        X-Roles: heat_stack_owner,_member_,admin
        X-Service-Catalog: [{"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:8774/v2/4537aca4a4a4462fa4c59ad5b5581f00", "region": "RegionOne", "publicURL": "http://172.21.7.40:8774/v2/4537aca4a4a4462fa4c59ad5b5581f00", "internalURL": "http://172.21.7.40:8774/v2/4537aca4a4a4462fa4c59ad5b5581f00", "id": "16b15cc5ff504cb89f58664e27a69c69"}], "type": "compute", "name": "nova"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:9696/", "region": "RegionOne", "publicURL": "http://172.21.7.40:9696/", "internalURL": "http://172.21.7.40:9696/", "id": "1b293a81696b4b7f896ead4622a1c2a1"}], "type": "network", "name": "neutron"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:8776/v2/4537aca4a4a4462fa4c59ad5b5581f00", "region": "RegionOne", "publicURL": "http://172.21.7.40:8776/v2/4537aca4a4a4462fa4c59ad5b5581f00", "internalURL": "http://172.21.7.40:8776/v2/4537aca4a4a4462fa4c59ad5b5581f00", "id": "3a7679cce7df4acfa16b3ca52ddcfc82"}], "type": "volumev2", "name": "cinderv2"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:8774/v3", "region": "RegionOne", "publicURL": "http://172.21.7.40:8774/v3", "internalURL": "http://172.21.7.40:8774/v3", "id": "0bb1d1b88afe40da93bcb1584ca17fb9"}], "type": "computev3", "name": "novav3"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:8080", "region": "RegionOne", "publicURL": "http://172.21.7.40:8080", "internalURL": "http://172.21.7.40:8080", "id": "1e32e172e79c4c5aa6b5c7f8d75af4fb"}], "type": "s3", "name": "swift_s3"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:9292", "region": "RegionOne", "publicURL": "http://172.21.7.40:9292", "internalURL": "http://172.21.7.40:9292", "id": "3d1c792651a049c5a61e35bfefc4c88b"}], "type": "image", "name": "glance"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:8777", "region": "RegionOne", "publicURL": "http://172.21.7.40:8777", "internalURL": "http://172.21.7.40:8777", "id": "39a4c06423a8493c928da18f4a5ccc1f"}], "type": "metering", "name": "ceilometer"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:8000/v1/", "region": "RegionOne", "publicURL": "http://172.21.7.40:8000/v1/", "internalURL": "http://172.21.7.40:8000/v1/", "id": "5570b8f811494e1b955db6e503df2afd"}], "type": "cloudformation", "name": "heat-cfn"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:8776/v1/4537aca4a4a4462fa4c59ad5b5581f00", "region": "RegionOne", "publicURL": "http://172.21.7.40:8776/v1/4537aca4a4a4462fa4c59ad5b5581f00", "internalURL": "http://172.21.7.40:8776/v1/4537aca4a4a4462fa4c59ad5b5581f00", "id": "0a1c8da4f156495aad2130e2c0691982"}], "type": "volume", "name": "cinder"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:8773/services/Admin", "region": "RegionOne", "publicURL": "http://172.21.7.40:8773/services/Cloud", "internalURL": "http://172.21.7.40:8773/services/Cloud", "id": "033f67e9500c49ca8f8b1893e2a7edaf"}], "type": "ec2", "name": "nova_ec2"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:8004/v1/4537aca4a4a4462fa4c59ad5b5581f00", "region": "RegionOne", "publicURL": "http://172.21.7.40:8004/v1/4537aca4a4a4462fa4c59ad5b5581f00", "internalURL": "http://172.21.7.40:8004/v1/4537aca4a4a4462fa4c59ad5b5581f00", "id": "4beb644253ae477f9e9496eedd1093a5"}], "type": "orchestration", "name": "heat"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:8080/", "region": "RegionOne", "publicURL": "http://172.21.7.40:8080/v1/AUTH_4537aca4a4a4462fa4c59ad5b5581f00", "internalURL": "http://172.21.7.40:8080/v1/AUTH_4537aca4a4a4462fa4c59ad5b5581f00", "id": "3a106354261043299a5d247e5f2594d2"}], "type": "object-store", "name": "swift"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:35357/v2.0", "region": "RegionOne", "publicURL": "http://172.21.7.40:5000/v2.0", "internalURL": "http://172.21.7.40:5000/v2.0", "id": "5c4ee7c31184424c942a1c52818572fb"}], "type": "identity", "name": "keystone"}]
        X-Tenant: admin
        X-Tenant-Id: 4537aca4a4a4462fa4c59ad5b5581f00
        X-Tenant-Name: admin
        X-User: admin
        X-User-Domain-Id: default
        X-User-Domain-Name: Default
        X-User-Id: 91d732b65831491d8bd952b3111e62dd
        X-User-Name: admin
        
        action = detail
        content_type = None
        body = 
        ======================================================================================
        """
        """
        如果action不等于'action'，则：
        meth = action
        meth_extensions = self.wsgi_extensions.get(action, [])
        即从@wsgi.extends修饰的没有action参数的扩展方法中选取，作为meth对应的扩展方法；
        
        如果action等于'action'，则：
        meth = self.wsgi_actions[action_name]
        即从@wsgi.actions修饰的扩展方法中选取，作为meth方法；
        meth_extensions = self.wsgi_action_extensions.get(action_name, [])
        即从@wsgi.extends修饰的有action参数的扩展方法中选取，作为meth对应的扩展方法；
        """

        # Look up the method
        try:
            if not self.controller:
                meth = getattr(self, action)
            else:
                meth = getattr(self.controller, action)
        except AttributeError:
            if (not self.wsgi_actions or
                    action not in _ROUTES_METHODS + ['action']):
                # Propagate the error
                raise
        else:
            return meth, self.wsgi_extensions.get(action, [])

        if action == 'action':
            # OK, it's an action; figure out which action...
            mtype = _MEDIA_TYPE_MAP.get(content_type)
            action_name = self.action_peek[mtype](body)
        else:
            action_name = action

        # Look up the action method
        return (self.wsgi_actions[action_name],
                self.wsgi_action_extensions.get(action_name, []))

    def dispatch(self, method, request, action_args):
        """
        Dispatch a call to the action-specific method.
        """
        """
        meth = <bound method Controller.detail of <nova.api.openstack.compute.servers.Controller object at 0x29b0e50>>
        action_args = {}
                    
        request = GET /v2/4537aca4a4a4462fa4c59ad5b5581f00/servers/detail HTTP/1.0
        Accept: application/json
        Accept-Encoding: gzip, deflate, compress
        Content-Type: text/plain
        Host: 172.21.7.40:8774
        User-Agent: python-novaclient
        X-Auth-Project-Id: admin
        X-Auth-Token: MIIT9wYJKoZIhvcNAQcCoIIT6DCCE+QCAQExCTAHBgUrDgMCGjCCEk0GCSqGSIb3DQEHAaCCEj4EghI6eyJhY2Nlc3MiOiB7InRva2VuIjogeyJpc3N1ZWRfYXQiOiAiMjAxNS0wMy0xOFQwNzoyMjo0OS42MTMzMzgiLCAiZXhwaXJlcyI6ICIyMDE1LTAzLTE4VDA4OjIyOjQ5WiIsICJpZCI6ICJwbGFjZWhvbGRlciIsICJ0ZW5hbnQiOiB7ImRlc2NyaXB0aW9uIjogImFkbWluIHRlbmFudCIsICJlbmFibGVkIjogdHJ1ZSwgImlkIjogIjQ1MzdhY2E0YTRhNDQ2MmZhNGM1OWFkNWI1NTgxZjAwIiwgIm5hbWUiOiAiYWRtaW4ifX0sICJzZXJ2aWNlQ2F0YWxvZyI6IFt7ImVuZHBvaW50cyI6IFt7ImFkbWluVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo4Nzc0L3YyLzQ1MzdhY2E0YTRhNDQ2MmZhNGM1OWFkNWI1NTgxZjAwIiwgInJlZ2lvbiI6ICJSZWdpb25PbmUiLCAiaW50ZXJuYWxVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjg3NzQvdjIvNDUzN2FjYTRhNGE0NDYyZmE0YzU5YWQ1YjU1ODFmMDAiLCAiaWQiOiAiMTZiMTVjYzVmZjUwNGNiODlmNTg2NjRlMjdhNjljNjkiLCAicHVibGljVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo4Nzc0L3YyLzQ1MzdhY2E0YTRhNDQ2MmZhNGM1OWFkNWI1NTgxZjAwIn1dLCAiZW5kcG9pbnRzX2xpbmtzIjogW10sICJ0eXBlIjogImNvbXB1dGUiLCAibmFtZSI6ICJub3ZhIn0sIHsiZW5kcG9pbnRzIjogW3siYWRtaW5VUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjk2OTYvIiwgInJlZ2lvbiI6ICJSZWdpb25PbmUiLCAiaW50ZXJuYWxVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjk2OTYvIiwgImlkIjogIjFiMjkzYTgxNjk2YjRiN2Y4OTZlYWQ0NjIyYTFjMmExIiwgInB1YmxpY1VSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6OTY5Ni8ifV0sICJlbmRwb2ludHNfbGlua3MiOiBbXSwgInR5cGUiOiAibmV0d29yayIsICJuYW1lIjogIm5ldXRyb24ifSwgeyJlbmRwb2ludHMiOiBbeyJhZG1pblVSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODc3Ni92Mi80NTM3YWNhNGE0YTQ0NjJmYTRjNTlhZDViNTU4MWYwMCIsICJyZWdpb24iOiAiUmVnaW9uT25lIiwgImludGVybmFsVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo4Nzc2L3YyLzQ1MzdhY2E0YTRhNDQ2MmZhNGM1OWFkNWI1NTgxZjAwIiwgImlkIjogIjNhNzY3OWNjZTdkZjRhY2ZhMTZiM2NhNTJkZGNmYzgyIiwgInB1YmxpY1VSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODc3Ni92Mi80NTM3YWNhNGE0YTQ0NjJmYTRjNTlhZDViNTU4MWYwMCJ9XSwgImVuZHBvaW50c19saW5rcyI6IFtdLCAidHlwZSI6ICJ2b2x1bWV2MiIsICJuYW1lIjogImNpbmRlcnYyIn0sIHsiZW5kcG9pbnRzIjogW3siYWRtaW5VUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjg3NzQvdjMiLCAicmVnaW9uIjogIlJlZ2lvbk9uZSIsICJpbnRlcm5hbFVSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODc3NC92MyIsICJpZCI6ICIwYmIxZDFiODhhZmU0MGRhOTNiY2IxNTg0Y2ExN2ZiOSIsICJwdWJsaWNVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjg3NzQvdjMifV0sICJlbmRwb2ludHNfbGlua3MiOiBbXSwgInR5cGUiOiAiY29tcHV0ZXYzIiwgIm5hbWUiOiAibm92YXYzIn0sIHsiZW5kcG9pbnRzIjogW3siYWRtaW5VUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjgwODAiLCAicmVnaW9uIjogIlJlZ2lvbk9uZSIsICJpbnRlcm5hbFVSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODA4MCIsICJpZCI6ICIxZTMyZTE3MmU3OWM0YzVhYTZiNWM3ZjhkNzVhZjRmYiIsICJwdWJsaWNVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjgwODAifV0sICJlbmRwb2ludHNfbGlua3MiOiBbXSwgInR5cGUiOiAiczMiLCAibmFtZSI6ICJzd2lmdF9zMyJ9LCB7ImVuZHBvaW50cyI6IFt7ImFkbWluVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo5MjkyIiwgInJlZ2lvbiI6ICJSZWdpb25PbmUiLCAiaW50ZXJuYWxVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjkyOTIiLCAiaWQiOiAiM2QxYzc5MjY1MWEwNDljNWE2MWUzNWJmZWZjNGM4OGIiLCAicHVibGljVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo5MjkyIn1dLCAiZW5kcG9pbnRzX2xpbmtzIjogW10sICJ0eXBlIjogImltYWdlIiwgIm5hbWUiOiAiZ2xhbmNlIn0sIHsiZW5kcG9pbnRzIjogW3siYWRtaW5VUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjg3NzciLCAicmVnaW9uIjogIlJlZ2lvbk9uZSIsICJpbnRlcm5hbFVSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODc3NyIsICJpZCI6ICIzOWE0YzA2NDIzYTg0OTNjOTI4ZGExOGY0YTVjY2MxZiIsICJwdWJsaWNVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjg3NzcifV0sICJlbmRwb2ludHNfbGlua3MiOiBbXSwgInR5cGUiOiAibWV0ZXJpbmciLCAibmFtZSI6ICJjZWlsb21ldGVyIn0sIHsiZW5kcG9pbnRzIjogW3siYWRtaW5VUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjgwMDAvdjEvIiwgInJlZ2lvbiI6ICJSZWdpb25PbmUiLCAiaW50ZXJuYWxVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjgwMDAvdjEvIiwgImlkIjogIjU1NzBiOGY4MTE0OTRlMWI5NTVkYjZlNTAzZGYyYWZkIiwgInB1YmxpY1VSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODAwMC92MS8ifV0sICJlbmRwb2ludHNfbGlua3MiOiBbXSwgInR5cGUiOiAiY2xvdWRmb3JtYXRpb24iLCAibmFtZSI6ICJoZWF0LWNmbiJ9LCB7ImVuZHBvaW50cyI6IFt7ImFkbWluVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo4Nzc2L3YxLzQ1MzdhY2E0YTRhNDQ2MmZhNGM1OWFkNWI1NTgxZjAwIiwgInJlZ2lvbiI6ICJSZWdpb25PbmUiLCAiaW50ZXJuYWxVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjg3NzYvdjEvNDUzN2FjYTRhNGE0NDYyZmE0YzU5YWQ1YjU1ODFmMDAiLCAiaWQiOiAiMGExYzhkYTRmMTU2NDk1YWFkMjEzMGUyYzA2OTE5ODIiLCAicHVibGljVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo4Nzc2L3YxLzQ1MzdhY2E0YTRhNDQ2MmZhNGM1OWFkNWI1NTgxZjAwIn1dLCAiZW5kcG9pbnRzX2xpbmtzIjogW10sICJ0eXBlIjogInZvbHVtZSIsICJuYW1lIjogImNpbmRlciJ9LCB7ImVuZHBvaW50cyI6IFt7ImFkbWluVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo4NzczL3NlcnZpY2VzL0FkbWluIiwgInJlZ2lvbiI6ICJSZWdpb25PbmUiLCAiaW50ZXJuYWxVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjg3NzMvc2VydmljZXMvQ2xvdWQiLCAiaWQiOiAiMDMzZjY3ZTk1MDBjNDljYThmOGIxODkzZTJhN2VkYWYiLCAicHVibGljVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo4NzczL3NlcnZpY2VzL0Nsb3VkIn1dLCAiZW5kcG9pbnRzX2xpbmtzIjogW10sICJ0eXBlIjogImVjMiIsICJuYW1lIjogIm5vdmFfZWMyIn0sIHsiZW5kcG9pbnRzIjogW3siYWRtaW5VUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjgwMDQvdjEvNDUzN2FjYTRhNGE0NDYyZmE0YzU5YWQ1YjU1ODFmMDAiLCAicmVnaW9uIjogIlJlZ2lvbk9uZSIsICJpbnRlcm5hbFVSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODAwNC92MS80NTM3YWNhNGE0YTQ0NjJmYTRjNTlhZDViNTU4MWYwMCIsICJpZCI6ICI0YmViNjQ0MjUzYWU0NzdmOWU5NDk2ZWVkZDEwOTNhNSIsICJwdWJsaWNVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjgwMDQvdjEvNDUzN2FjYTRhNGE0NDYyZmE0YzU5YWQ1YjU1ODFmMDAifV0sICJlbmRwb2ludHNfbGlua3MiOiBbXSwgInR5cGUiOiAib3JjaGVzdHJhdGlvbiIsICJuYW1lIjogImhlYXQifSwgeyJlbmRwb2ludHMiOiBbeyJhZG1pblVSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODA4MC8iLCAicmVnaW9uIjogIlJlZ2lvbk9uZSIsICJpbnRlcm5hbFVSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODA4MC92MS9BVVRIXzQ1MzdhY2E0YTRhNDQ2MmZhNGM1OWFkNWI1NTgxZjAwIiwgImlkIjogIjNhMTA2MzU0MjYxMDQzMjk5YTVkMjQ3ZTVmMjU5NGQyIiwgInB1YmxpY1VSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODA4MC92MS9BVVRIXzQ1MzdhY2E0YTRhNDQ2MmZhNGM1OWFkNWI1NTgxZjAwIn1dLCAiZW5kcG9pbnRzX2xpbmtzIjogW10sICJ0eXBlIjogIm9iamVjdC1zdG9yZSIsICJuYW1lIjogInN3aWZ0In0sIHsiZW5kcG9pbnRzIjogW3siYWRtaW5VUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjM1MzU3L3YyLjAiLCAicmVnaW9uIjogIlJlZ2lvbk9uZSIsICJpbnRlcm5hbFVSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6NTAwMC92Mi4wIiwgImlkIjogIjVjNGVlN2MzMTE4NDQyNGM5NDJhMWM1MjgxODU3MmZiIiwgInB1YmxpY1VSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6NTAwMC92Mi4wIn1dLCAiZW5kcG9pbnRzX2xpbmtzIjogW10sICJ0eXBlIjogImlkZW50aXR5IiwgIm5hbWUiOiAia2V5c3RvbmUifV0sICJ1c2VyIjogeyJ1c2VybmFtZSI6ICJhZG1pbiIsICJyb2xlc19saW5rcyI6IFtdLCAiaWQiOiAiOTFkNzMyYjY1ODMxNDkxZDhiZDk1MmIzMTExZTYyZGQiLCAicm9sZXMiOiBbeyJuYW1lIjogImhlYXRfc3RhY2tfb3duZXIifSwgeyJuYW1lIjogIl9tZW1iZXJfIn0sIHsibmFtZSI6ICJhZG1pbiJ9XSwgIm5hbWUiOiAiYWRtaW4ifSwgIm1ldGFkYXRhIjogeyJpc19hZG1pbiI6IDAsICJyb2xlcyI6IFsiZDlmZGVlODI1NjE3NGJlNWE3MmFjZGZmNDNkM2VkZDMiLCAiOWZlMmZmOWVlNDM4NGIxODk0YTkwODc4ZDNlOTJiYWIiLCAiN2E1ZTg5MmFiYTE5NDI3NWI3ZjQxZWM4Njg2ZDUwOGYiXX19fTGCAYEwggF9AgEBMFwwVzELMAkGA1UEBhMCVVMxDjAMBgNVBAgMBVVuc2V0MQ4wDAYDVQQHDAVVbnNldDEOMAwGA1UECgwFVW5zZXQxGDAWBgNVBAMMD3d3dy5leGFtcGxlLmNvbQIBATAHBgUrDgMCGjANBgkqhkiG9w0BAQEFAASCAQBkjJ1obp-dG+uEHilZdGvCQu3cmPsI5Atz78lO+iEJea6C5-OQCaLCpdAOd3rbZqn75OKWjbs9GVbXigkpLSKrRyd9U5jJOcxXP6iWIpVr3XE6YjGMlGbfP6W8pBmmc1IvSAgFfie9FUgsBeMDk-wSbggPKsmugKWAkf8e71s6ZQQ5LN65Y6+Orkst03Fojr96XCfpaOPOh19k5FgvKOCFUPKVKpqTio-1W14--wcnrmDU+tOqLDpICQm0QSAOHrX59JVHB0YGy9aCSDocG3pzumxZU1YorDqJCgiUZyAamw9iwzEHVveIko0dIUwy5iipejq+bkmyjb+FyOjZqfCH
        X-Domain-Id: None
        X-Domain-Name: None
        X-Identity-Status: Confirmed
        X-Project-Domain-Id: default
        X-Project-Domain-Name: Default
        X-Project-Id: 4537aca4a4a4462fa4c59ad5b5581f00
        X-Project-Name: admin
        X-Role: heat_stack_owner,_member_,admin
        X-Roles: heat_stack_owner,_member_,admin
        X-Service-Catalog: [{"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:8774/v2/4537aca4a4a4462fa4c59ad5b5581f00", "region": "RegionOne", "publicURL": "http://172.21.7.40:8774/v2/4537aca4a4a4462fa4c59ad5b5581f00", "internalURL": "http://172.21.7.40:8774/v2/4537aca4a4a4462fa4c59ad5b5581f00", "id": "16b15cc5ff504cb89f58664e27a69c69"}], "type": "compute", "name": "nova"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:9696/", "region": "RegionOne", "publicURL": "http://172.21.7.40:9696/", "internalURL": "http://172.21.7.40:9696/", "id": "1b293a81696b4b7f896ead4622a1c2a1"}], "type": "network", "name": "neutron"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:8776/v2/4537aca4a4a4462fa4c59ad5b5581f00", "region": "RegionOne", "publicURL": "http://172.21.7.40:8776/v2/4537aca4a4a4462fa4c59ad5b5581f00", "internalURL": "http://172.21.7.40:8776/v2/4537aca4a4a4462fa4c59ad5b5581f00", "id": "3a7679cce7df4acfa16b3ca52ddcfc82"}], "type": "volumev2", "name": "cinderv2"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:8774/v3", "region": "RegionOne", "publicURL": "http://172.21.7.40:8774/v3", "internalURL": "http://172.21.7.40:8774/v3", "id": "0bb1d1b88afe40da93bcb1584ca17fb9"}], "type": "computev3", "name": "novav3"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:8080", "region": "RegionOne", "publicURL": "http://172.21.7.40:8080", "internalURL": "http://172.21.7.40:8080", "id": "1e32e172e79c4c5aa6b5c7f8d75af4fb"}], "type": "s3", "name": "swift_s3"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:9292", "region": "RegionOne", "publicURL": "http://172.21.7.40:9292", "internalURL": "http://172.21.7.40:9292", "id": "3d1c792651a049c5a61e35bfefc4c88b"}], "type": "image", "name": "glance"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:8777", "region": "RegionOne", "publicURL": "http://172.21.7.40:8777", "internalURL": "http://172.21.7.40:8777", "id": "39a4c06423a8493c928da18f4a5ccc1f"}], "type": "metering", "name": "ceilometer"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:8000/v1/", "region": "RegionOne", "publicURL": "http://172.21.7.40:8000/v1/", "internalURL": "http://172.21.7.40:8000/v1/", "id": "5570b8f811494e1b955db6e503df2afd"}], "type": "cloudformation", "name": "heat-cfn"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:8776/v1/4537aca4a4a4462fa4c59ad5b5581f00", "region": "RegionOne", "publicURL": "http://172.21.7.40:8776/v1/4537aca4a4a4462fa4c59ad5b5581f00", "internalURL": "http://172.21.7.40:8776/v1/4537aca4a4a4462fa4c59ad5b5581f00", "id": "0a1c8da4f156495aad2130e2c0691982"}], "type": "volume", "name": "cinder"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:8773/services/Admin", "region": "RegionOne", "publicURL": "http://172.21.7.40:8773/services/Cloud", "internalURL": "http://172.21.7.40:8773/services/Cloud", "id": "033f67e9500c49ca8f8b1893e2a7edaf"}], "type": "ec2", "name": "nova_ec2"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:8004/v1/4537aca4a4a4462fa4c59ad5b5581f00", "region": "RegionOne", "publicURL": "http://172.21.7.40:8004/v1/4537aca4a4a4462fa4c59ad5b5581f00", "internalURL": "http://172.21.7.40:8004/v1/4537aca4a4a4462fa4c59ad5b5581f00", "id": "4beb644253ae477f9e9496eedd1093a5"}], "type": "orchestration", "name": "heat"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:8080/", "region": "RegionOne", "publicURL": "http://172.21.7.40:8080/v1/AUTH_4537aca4a4a4462fa4c59ad5b5581f00", "internalURL": "http://172.21.7.40:8080/v1/AUTH_4537aca4a4a4462fa4c59ad5b5581f00", "id": "3a106354261043299a5d247e5f2594d2"}], "type": "object-store", "name": "swift"}, {"endpoints_links": [], "endpoints": [{"adminURL": "http://172.21.7.40:35357/v2.0", "region": "RegionOne", "publicURL": "http://172.21.7.40:5000/v2.0", "internalURL": "http://172.21.7.40:5000/v2.0", "id": "5c4ee7c31184424c942a1c52818572fb"}], "type": "identity", "name": "keystone"}]
        X-Tenant: admin
        X-Tenant-Id: 4537aca4a4a4462fa4c59ad5b5581f00
        X-Tenant-Name: admin
        X-User: admin
        X-User-Domain-Id: default
        X-User-Domain-Name: Default
        X-User-Id: 91d732b65831491d8bd952b3111e62dd
        X-User-Name: admin
        """

        """
        return:
        ======================================================================================
        servers = {'servers': [{'status': 'SHUTOFF', 'updated': '2015-03-17T16:59:39Z', 'hostId': '80edf4278faf2e792eedcf39ba7cda12df2169bdaad7ea118081e07f', 'addresses': {}, 'links': [{'href': u'http://172.21.6.180:8774/v2/2a3cc2062e154e148b50e79ed3736e4a/servers/770ae6a2-f7dc-4f90-af0e-361bb22ce9cc', 'rel': 'self'}, {'href': u'http://172.21.6.180:8774/2a3cc2062e154e148b50e79ed3736e4a/servers/770ae6a2-f7dc-4f90-af0e-361bb22ce9cc', 'rel': 'bookmark'}], 'image': {'id': 'd407bd3e-aa1c-49ea-bc84-00584182b283', 'links': [{'href': u'http://172.21.6.180:8774/2a3cc2062e154e148b50e79ed3736e4a/images/d407bd3e-aa1c-49ea-bc84-00584182b283', 'rel': 'bookmark'}]}, 'flavor': {'id': '1', 'links': [{'href': u'http://172.21.6.180:8774/2a3cc2062e154e148b50e79ed3736e4a/flavors/1', 'rel': 'bookmark'}]}, 'id': '770ae6a2-f7dc-4f90-af0e-361bb22ce9cc', 'user_id': u'c01f7e46dfe84393bc214626edebc959', 'name': u'test0', 'created': '2015-03-17T15:24:46Z', 'tenant_id': u'2a3cc2062e154e148b50e79ed3736e4a', 'accessIPv4': '', 'accessIPv6': '', 'metadata': {}}]}
        ======================================================================================
        """
        return method(req=request, **action_args)


def action(name):
    """
    Mark a function as an action.

    The given name will be taken as the action key in the body.

    This is also overloaded to allow extensions to provide
    non-extending definitions of create and delete operations.
    """

    def decorator(func):
        func.wsgi_action = name
        return func
    return decorator


def extends(*args, **kwargs):
    """
    Indicate a function extends an operation.

    Can be used as either::

        @extends
        def index(...):
            pass

    or as::

        @extends(action='resize')
        def _action_resize(...):
            pass
    """

    def decorator(func):
        # Store enough information to find what we're extending
        func.wsgi_extends = (func.__name__, kwargs.get('action'))
        return func

    # If we have positional arguments, call the decorator
    if args:
        return decorator(*args)

    # OK, return the decorator instead
    return decorator


class ControllerMetaclass(type):
    """
    Controller metaclass.

    This metaclass automates the task of assembling a dictionary
    mapping action keys to method names.
    """

    def __new__(self, mcs, name, bases, cls_dict):
        """
        Adds the wsgi_actions dictionary to the class.
        """

        # Find all actions
        actions = {}
        extensions = []
        # start with wsgi actions from base classes
        for base in bases:
            actions.update(getattr(base, 'wsgi_actions', {}))
        for key, value in cls_dict.items():
            if not callable(value):
                continue
            if getattr(value, 'wsgi_action', None):
                actions[value.wsgi_action] = key
            elif getattr(value, 'wsgi_extends', None):
                extensions.append(value.wsgi_extends)

        # Add the actions and extensions to the class dict
        cls_dict['wsgi_actions'] = actions
        cls_dict['wsgi_extensions'] = extensions

        return super(ControllerMetaclass, mcs).__new__(mcs, name, bases,
                                                       cls_dict)


@six.add_metaclass(ControllerMetaclass)
class Controller(object):
    """
    Default controller.
    """

    _view_builder_class = None

    def __init__(self, view_builder=None):
        """Initialize controller with a view builder instance."""
        if view_builder:
            self._view_builder = view_builder
        elif self._view_builder_class:
            self._view_builder = self._view_builder_class()
        else:
            self._view_builder = None

    @staticmethod
    def is_valid_body(body, entity_name):
        if not (body and entity_name in body):
            return False

        def is_dict(d):
            try:
                d.get(None)
                return True
            except AttributeError:
                return False

        if not is_dict(body[entity_name]):
            return False

        return True


class Fault(webob.exc.HTTPException):
    """
    Wrap webob.exc.HTTPException to provide API friendly response.
    """

    _fault_names = {
            400: "badRequest",
            401: "unauthorized",
            403: "forbidden",
            404: "itemNotFound",
            405: "badMethod",
            409: "conflictingRequest",
            413: "overLimit",
            415: "badMediaType",
            429: "overLimit",
            501: "notImplemented",
            503: "serviceUnavailable"}

    def __init__(self, exception):
        """
        Create a Fault for the given webob.exc.exception.
        """
        self.wrapped_exc = exception
        for key, value in self.wrapped_exc.headers.items():
            self.wrapped_exc.headers[key] = str(value)
        self.status_int = exception.status_int

    @webob.dec.wsgify(RequestClass=Request)
    def __call__(self, req):
        """
        Generate a WSGI response based on the exception passed to ctor.
        """

        user_locale = req.best_match_language()
        # Replace the body with fault details.
        code = self.wrapped_exc.status_int
        fault_name = self._fault_names.get(code, "computeFault")
        explanation = self.wrapped_exc.explanation
        LOG.debug(_("Returning %(code)s to user: %(explanation)s"),
                  {'code': code, 'explanation': explanation})

        explanation = gettextutils.translate(explanation,
                                                         user_locale)
        fault_data = {
            fault_name: {
                'code': code,
                'message': explanation}}
        if code == 413 or code == 429:
            retry = self.wrapped_exc.headers.get('Retry-After', None)
            if retry:
                fault_data[fault_name]['retryAfter'] = retry

        # 'code' is an attribute on the fault tag itself
        metadata = {'attributes': {fault_name: 'code'}}

        xml_serializer = XMLDictSerializer(metadata, XMLNS_V11)

        content_type = req.best_match_content_type()
        serializer = {
            'application/xml': xml_serializer,
            'application/json': JSONDictSerializer(),
        }[content_type]

        self.wrapped_exc.body = serializer.serialize(fault_data)
        self.wrapped_exc.content_type = content_type
        _set_request_id_header(req, self.wrapped_exc.headers)

        return self.wrapped_exc

    def __str__(self):
        return self.wrapped_exc.__str__()


class RateLimitFault(webob.exc.HTTPException):
    """
    Rate-limited request response.
    """

    def __init__(self, message, details, retry_time):
        """
        Initialize new `RateLimitFault` with relevant information.
        """
        hdrs = RateLimitFault._retry_after(retry_time)
        self.wrapped_exc = webob.exc.HTTPTooManyRequests(headers=hdrs)
        self.content = {
            "overLimit": {
                "code": self.wrapped_exc.status_int,
                "message": message,
                "details": details,
                "retryAfter": hdrs['Retry-After'],
            },
        }

    @staticmethod
    def _retry_after(retry_time):
        delay = int(math.ceil(retry_time - time.time()))
        retry_after = delay if delay > 0 else 0
        headers = {'Retry-After': '%d' % retry_after}
        return headers

    @webob.dec.wsgify(RequestClass=Request)
    def __call__(self, request):
        """
        Return the wrapped exception with a serialized body conforming
        to our error format.
        """
        user_locale = request.best_match_language()
        content_type = request.best_match_content_type()
        metadata = {"attributes": {"overLimit": ["code", "retryAfter"]}}

        self.content['overLimit']['message'] = \
                gettextutils.translate(
                        self.content['overLimit']['message'],
                        user_locale)
        self.content['overLimit']['details'] = \
                gettextutils.translate(
                        self.content['overLimit']['details'],
                        user_locale)

        xml_serializer = XMLDictSerializer(metadata, XMLNS_V11)
        serializer = {
            'application/xml': xml_serializer,
            'application/json': JSONDictSerializer(),
        }[content_type]

        content = serializer.serialize(self.content)
        self.wrapped_exc.body = content
        self.wrapped_exc.content_type = content_type

        return self.wrapped_exc


def _set_request_id_header(req, headers):
    context = req.environ.get('nova.context')
    if context:
        headers['x-compute-request-id'] = context.request_id