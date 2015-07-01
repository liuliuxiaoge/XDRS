"""
用于实现功能扩展的若干实现类；
"""

import abc
import functools
import os

import six
import webob.dec
import webob.exc

import xdrs.api.openstack
from xdrs.api.openstack import wsgi
from xdrs.api.openstack import xmlutil
from xdrs import exception
from xdrs.openstack.common.gettextutils import _
from xdrs.openstack.common import importutils
from xdrs.openstack.common import log as logging
import xdrs.policy

LOG = logging.getLogger(__name__)


class ExtensionDescriptor(object):
    """
    用于功能扩展实现的基类；
    """

    # The name of the extension, e.g., 'Fox In Socks'
    name = None

    # The alias for the extension, e.g., 'FOXNSOX'
    alias = None

    # Description comes from the docstring for the class

    # The XML namespace for the extension, e.g.,
    # 'http://www.fox.in.socks/api/ext/pie/v1.0'
    namespace = None

    # The timestamp when the extension was last updated, e.g.,
    # '2011-01-22T13:25:27-06:00'
    updated = None

    def __init__(self, ext_mgr):
        """
        Register extension with the extension manager.
        """

        ext_mgr.register(self)
        self.ext_mgr = ext_mgr

    def get_resources(self):
        """
        List of extensions.ResourceExtension extension objects.
        Resources define new nouns, and are accessible through URLs.
        """
        resources = []
        return resources

    def get_controller_extensions(self):
        """
        List of extensions.ControllerExtension extension objects.
        Controller extensions are used to extend existing controllers.
        """
        controller_exts = []
        return controller_exts

    @classmethod
    def nsmap(cls):
        """
        Synthesize a namespace map from extension.
        """

        # Start with a base nsmap
        nsmap = ext_nsmap.copy()

        # Add the namespace for the extension
        nsmap[cls.alias] = cls.namespace

        return nsmap

    @classmethod
    def xmlname(cls, name):
        """
        Synthesize element and attribute names.
        """

        return '{%s}%s' % (cls.namespace, name)


def make_ext(elem):
    elem.set('name')
    elem.set('namespace')
    elem.set('alias')
    elem.set('updated')

    desc = xmlutil.SubTemplateElement(elem, 'description')
    desc.text = 'description'

    xmlutil.make_links(elem, 'links')


ext_nsmap = {None: xmlutil.XMLNS_COMMON_V10, 'atom': xmlutil.XMLNS_ATOM}


class ExtensionTemplate(xmlutil.TemplateBuilder):
    def construct(self):
        root = xmlutil.TemplateElement('extension', selector='extension')
        make_ext(root)
        return xmlutil.MasterTemplate(root, 1, nsmap=ext_nsmap)


class ExtensionsTemplate(xmlutil.TemplateBuilder):
    def construct(self):
        root = xmlutil.TemplateElement('extensions')
        elem = xmlutil.SubTemplateElement(root, 'extension',
                                          selector='extensions')
        make_ext(elem)
        return xmlutil.MasterTemplate(root, 1, nsmap=ext_nsmap)


class ExtensionsController(wsgi.Resource):

    def __init__(self, extension_manager):
        self.extension_manager = extension_manager
        super(ExtensionsController, self).__init__(None)

    def _translate(self, ext):
        ext_data = {}
        ext_data['name'] = ext.name
        ext_data['alias'] = ext.alias
        ext_data['description'] = ext.__doc__
        ext_data['namespace'] = ext.namespace
        ext_data['updated'] = ext.updated
        ext_data['links'] = []  # TODO(dprince): implement extension links
        return ext_data

    @wsgi.serializers(xml=ExtensionsTemplate)
    def index(self, req):
        extensions = []
        for ext in self.extension_manager.sorted_extensions():
            extensions.append(self._translate(ext))
        return dict(extensions=extensions)

    @wsgi.serializers(xml=ExtensionTemplate)
    def show(self, req, id):
        try:
            # NOTE(dprince): the extensions alias is used as the 'id' for show
            ext = self.extension_manager.extensions[id]
        except KeyError:
            raise webob.exc.HTTPNotFound()

        return dict(extension=self._translate(ext))

    def delete(self, req, id):
        raise webob.exc.HTTPNotFound()

    def create(self, req, body):
        raise webob.exc.HTTPNotFound()

class ExtensionManager(object):
    """
    Load extensions from the configured extension path.
    """
    def sorted_extensions(self):
        if self.sorted_ext_list is None:
            self.sorted_ext_list = sorted(self.extensions.iteritems())

        for _alias, ext in self.sorted_ext_list:
            yield ext

    def is_loaded(self, alias):
        return alias in self.extensions

    def register(self, ext):
        # Do nothing if the extension doesn't check out
        if not self._check_extension(ext):
            return

        alias = ext.alias
        LOG.audit(_('Loaded extension: %s'), alias)

        if alias in self.extensions:
            raise exception.XdrsException("Found duplicate extension: %s"
                                          % alias)
        self.extensions[alias] = ext
        self.sorted_ext_list = None

    def get_resources(self):
        """
        Returns a list of ResourceExtension objects.
        """

        resources = []
        resources.append(ResourceExtension('extensions',
                                           ExtensionsController(self)))
        for ext in self.sorted_extensions():
            """
            获取所有扩展文件的入口类；
            """
            try:
                resources.extend(ext.get_resources())
            except AttributeError:
                # NOTE(dprince): Extension aren't required to have resource
                # extensions
                pass
        return resources

    def get_controller_extensions(self):
        """
        Returns a list of ControllerExtension objects.
        获取所有扩展文件中具体实现了get_controller_extensions方法的集合；
        """
        controller_exts = []
        for ext in self.sorted_extensions():
            """
            获取所有扩展文件的入口类；
            """
            try:
                get_ext_method = ext.get_controller_extensions
                """
                获取所有扩展文件的get_controller_extensions方法，没有实现的，调用其父类中的方法；
                """

            except AttributeError:
                # NOTE(Vek): Extensions aren't required to have
                # controller extensions
                continue
            controller_exts.extend(get_ext_method())
        
        """
        ======================================================================================
        获取所有扩展文件中具体实现了get_controller_extensions方法的集合；
        具体实现了get_controller_extensions方法中都有具体的返回值，
        extension = extensions.ControllerExtension(......)
        """
        return controller_exts

    def _check_extension(self, extension):
        """
        Checks for required methods in extension objects.
        """
        try:
            LOG.debug(_('Ext name: %s'), extension.name)
            LOG.debug(_('Ext alias: %s'), extension.alias)
            LOG.debug(_('Ext description: %s'),
                      ' '.join(extension.__doc__.strip().split()))
            LOG.debug(_('Ext namespace: %s'), extension.namespace)
            LOG.debug(_('Ext updated: %s'), extension.updated)
        except AttributeError as ex:
            LOG.exception(_("Exception loading extension: %s"), unicode(ex))
            return False

        return True

    def load_extension(self, ext_factory):
        """
        Execute an extension factory.

        Loads an extension.  The 'ext_factory' is the name of a
        callable that will be imported and called with one
        argument--the extension manager.  The factory callable is
        expected to call the register() method at least once.
        """

        LOG.debug(_("Loading extension %s"), ext_factory)

        if isinstance(ext_factory, six.string_types):
            # Load the factory
            factory = importutils.import_class(ext_factory)
        else:
            factory = ext_factory

        # Call it
        LOG.debug(_("Calling extension factory %s"), ext_factory)
        factory(self)

    def _load_extensions(self):
        """
        Load extensions specified on the command line.
        加载所有的API扩展功能；
        """
        extensions = list(self.cls_list)
        """
        ======================================================================================
        self.cls_list = ['nova.api.openstack.compute.contrib.standard_extensions']
        extensions = ['nova.api.openstack.compute.contrib.standard_extensions']
        ======================================================================================
        """

        for ext_factory in extensions:
            try:
                self.load_extension(ext_factory)
            except Exception as exc:
                LOG.warn(_('Failed to load extension %(ext_factory)s: '
                           '%(exc)s'),
                         {'ext_factory': ext_factory, 'exc': exc})


class ControllerExtension(object):
    def __init__(self, extension, collection, controller):
        self.extension = extension
        self.collection = collection
        self.controller = controller


class ResourceExtension(object):
    def __init__(self, collection, controller=None, parent=None,
                 collection_actions=None, member_actions=None,
                 custom_routes_fn=None, inherits=None, member_name=None):
        if not collection_actions:
            collection_actions = {}
        if not member_actions:
            member_actions = {}
        self.collection = collection
        self.controller = controller
        self.parent = parent
        self.collection_actions = collection_actions
        self.member_actions = member_actions
        self.custom_routes_fn = custom_routes_fn
        self.inherits = inherits
        self.member_name = member_name


def load_standard_extensions(ext_mgr, logger, path, package, ext_list=None):
    """
    Registers all standard API extensions.
    注册所有标准的API扩展功能。
    @@@@注：在这里还只是实现API扩展功能的注册，还没有进行实质的功能扩展方法的调用；
    """
    """
    ======================================================================================
    ext_mgr = <nova.api.openstack.compute.extensions.ExtensionManager object at 0x33d9190>
    __path__ = ['/usr/lib/python2.7/site-packages/nova/api/openstack/compute/contrib']
    LOG = <nova.openstack.common.log.ContextAdapter object at 0x295d610>
    __package__ = nova.api.openstack.compute.contrib
    ======================================================================================
    """

    # Walk through all the modules in our directory...
    our_dir = path[0]
    """
    our_dir = /usr/lib/python2.7/site-packages/nova/api/openstack/compute/contrib
    """
    """
    1.获取contrib目录下所有的文件；
    2.过滤出以.py作为后缀的文件；
    3.针对每一个.py文件，获取其具有和其文件名相同的类名的类（每一个类都有），
      作为加载扩展API功能的入口；
    4.加载并调用所获取的每一个类，进行时间日期等参数的初始化；
      （这里还没有进行实质的功能扩展方法的调用；）
    """
    for dirpath, dirnames, filenames in os.walk(our_dir):
        """
        ======================================================================================
        filenames = 
        ['instance_actions.py', 'extended_hypervisors.pyo', 
         'extended_services_delete.pyo', 'os_networks.pyc', 
         'extended_floating_ips.pyc', 'migrations.pyo', 
         'server_external_events.pyc', 'floating_ips.pyc', 
         'user_data.py', 'os_networks.pyo', 'rescue.pyo', 
         'extended_virtual_interfaces_net.pyo', 'extended_floating_ips.pyo', 
         'baremetal_ext_status.pyo', 'server_start_stop.pyo', 
         'os_tenant_networks.pyc', 'scheduler_hints.py', 'image_size.py', 
         'rescue.py', 'block_device_mapping_v2_boot.pyo', 'quotas.pyc', 
         '__init__.pyo', 'extended_services.pyc', 'multinic.pyc', 'services.py', 
         'extended_services.py', 'extended_hypervisors.py', 'extended_quotas.pyo', 
         'preserve_ephemeral_rebuild.pyc', 'extended_status.pyo', 
         'baremetal_ext_status.py', 'security_groups.pyc', 
         'volume_attachment_update.py', 'floating_ip_pools.py', 
         'server_password.py', 'floating_ips_bulk.pyc', 'volumes.pyo', 
         'keypairs.pyo', 'flavormanage.pyc', 'extended_hypervisors.pyc', 
         'flavorextradata.pyc', 'extended_services.pyo', 'attach_interfaces.pyc', 
         'server_usage.pyo', 'networks_associate.pyo', 'multinic.pyo', 'evacuate.py', 
         'consoles.py', 'config_drive.pyo', 'hide_server_addresses.py', 
         'extended_availability_zone.py', 'security_group_default_rules.pyc', 
         'admin_actions.py', 'extended_services_delete.py', 
         'extended_availability_zone.pyo', 'aggregates.py', 
         'used_limits_for_admin.pyo', 'fixed_ips.pyc', 'cells.pyc', 
         'quota_classes.pyo', 'baremetal_ext_status.pyc', 'agents.pyo', 
         'deferred_delete.pyc', 'os_tenant_networks.py', 'cloudpipe.py', 
         'instance_usage_audit_log.pyc', 'extended_ips_mac.py', 
         'flavor_disabled.pyc', 'extended_quotas.py', 'cloudpipe.pyo', 
         'hosts.py', 'flavormanage.py', 'multiple_create.pyc', 'evacuate.pyo', 
         'console_output.pyc', 'shelve.pyc', 'volume_attachment_update.pyc', 
         'extended_services_delete.pyc', 'hypervisors.pyo', 'user_data.pyc', 
         'instance_usage_audit_log.pyo', 'floating_ips.py', 'baremetal_nodes.pyc', 
         'used_limits_for_admin.py', 'deferred_delete.py', 'cells.py', 
         'cloudpipe_update.py', 'cloudpipe.pyc', 'security_groups.pyo', 
         'fping.pyo', 'security_group_default_rules.py', 'virtual_interfaces.pyc', 
         'cloudpipe_update.pyo', 'availability_zone.pyc', 'used_limits.py', 
         'migrations.py', 'extended_floating_ips.py', 
         'extended_virtual_interfaces_net.py', 'floating_ip_dns.py', 
         'assisted_volume_snapshots.pyo', 'services.pyo', 'server_diagnostics.py', 
         'scheduler_hints.pyc', 'multinic.py', 'aggregates.pyo', 
         'flavor_disabled.py', 'quota_classes.py', 'flavor_rxtx.pyo', 
         'instance_usage_audit_log.py', 'server_groups.pyc', 'fixed_ips.py', 
         'extended_server_attributes.pyc', 'assisted_volume_snapshots.pyc', 
         'certificates.pyo', 'extended_ips_mac.pyo', 'baremetal_nodes.pyo', 
         'scheduler_hints.pyo', 'server_diagnostics.pyo', 
         'hide_server_addresses.pyc', 'floating_ips_bulk.pyo', 'consoles.pyo', 
         'baremetal_nodes.py', 'services.pyc', 'flavor_disabled.pyo', 
         'server_external_events.py', 'flavorextraspecs.py', 'agents.py', 
         'console_auth_tokens.pyc', 'flavorextradata.pyo', 'image_size.pyc', 
         'flavor_access.py', 'preserve_ephemeral_rebuild.py', 
         'instance_actions.pyo', 'volume_attachment_update.pyo', 'flavor_rxtx.pyc', 
         'extended_server_attributes.pyo', 'availability_zone.pyo', 
         'disk_config.pyc', '__init__.py', 'console_output.py', 'extended_ips.py', 
         'extended_availability_zone.pyc', 'hide_server_addresses.pyo', 
         'server_groups.pyo', 'image_size.pyo', 'createserverext.pyc', 
         'floating_ip_pools.pyo', 'quotas.py', 'server_diagnostics.pyc', 
         'disk_config.pyo', 'availability_zone.py', 'console_auth_tokens.pyo', 
         'server_usage.py', 'createserverext.py', 'server_start_stop.py', 
         'floating_ip_dns.pyo', 'admin_actions.pyc', 'multiple_create.py', 
         'keypairs.py', 'cell_capacities.pyc', 'console_auth_tokens.py', 
         'flavor_rxtx.py', 'preserve_ephemeral_rebuild.pyo', 'hypervisors.pyc', 
         'extended_volumes.pyc', 'hosts.pyc', 'floating_ip_pools.pyc', 
         'user_quotas.pyo', 'floating_ip_dns.pyc', 'createserverext.pyo', 
         'consoles.pyc', 'flavor_access.pyo', 'extended_ips.pyo', 
         'multiple_create.pyo', 'cells.pyo', 'flavor_swap.pyo', 
         'config_drive.py', 'deferred_delete.pyo', 'simple_tenant_usage.py', 
         'extended_ips_mac.pyc', 'flavor_swap.pyc', 'cloudpipe_update.pyc', 
         'extended_server_attributes.py', 'fping.py', 'user_quotas.py', 
         'hosts.pyo', 'flavorextraspecs.pyc', 'simple_tenant_usage.pyc', 
         'migrations.pyc', 'instance_actions.pyc', 'virtual_interfaces.pyo', 
         'extended_quotas.pyc', 'rescue.pyc', 'floating_ips_bulk.py', 
         'keypairs.pyc', 'certificates.pyc', 'disk_config.py', 
         'console_output.pyo', 'extended_volumes.py', 'fixed_ips.pyo', 
         'agents.pyc', 'fping.pyc', 'quota_classes.pyc', 'volumes.pyc', 
         'block_device_mapping_v2_boot.pyc', 'config_drive.pyc', 
         'virtual_interfaces.py', 'user_quotas.pyc', 'used_limits.pyc', 
         'certificates.py', 'flavor_swap.py', 'security_groups.py', 
         'extended_ips.pyc', 'extended_status.pyc', 'server_groups.py', 
         'used_limits_for_admin.pyc', 'floating_ips.pyo', 'aggregates.pyc', 
         'block_device_mapping_v2_boot.py', 'server_external_events.pyo', 
         'used_limits.pyo', 'networks_associate.py', 'hypervisors.py', 
         'server_usage.pyc', 'admin_actions.pyo', 'quotas.pyo', '__init__.pyc', 
         'shelve.pyo', 'os_tenant_networks.pyo', 'flavorextradata.py', 
         'server_password.pyo', 'cell_capacities.py', 
         'extended_virtual_interfaces_net.pyc', 'extended_status.py', 
         'server_password.pyc', 'volumes.py', 'evacuate.pyc', 
         'extended_volumes.pyo', 'networks_associate.pyc', 
         'attach_interfaces.pyo', 'server_start_stop.pyc', 'flavorextraspecs.pyo', 
         'attach_interfaces.py', 'flavormanage.pyo', 'shelve.py', 'user_data.pyo', 
         'simple_tenant_usage.pyo', 'cell_capacities.pyo', 
         'security_group_default_rules.pyo', 'assisted_volume_snapshots.py', 
         'flavor_access.pyc', 'os_networks.py']
        ======================================================================================
        """
        
        # Compute the relative package name from the dirpath
        relpath = os.path.relpath(dirpath, our_dir)
        if relpath == '.':
            relpkg = ''
        else:
            relpkg = '.%s' % '.'.join(relpath.split(os.sep))

        # Now, consider each file in turn, only considering .py files
        for fname in filenames:
            root, ext = os.path.splitext(fname)

            # Skip __init__ and anything that's not .py
            if ext != '.py' or root == '__init__':
                continue

            # Try loading it
            classname = "%s%s" % (root[0].upper(), root[1:])
            classpath = ("%s%s.%s.%s" %
                         (package, relpkg, root, classname))
            
            if ext_list is not None and classname not in ext_list:
                logger.debug("Skipping extension: %s" % classpath)
                continue

            try:
                ext_mgr.load_extension(classpath)
            except Exception as exc:
                logger.warn(_('Failed to load extension %(classpath)s: '
                              '%(exc)s'),
                            {'classpath': classpath, 'exc': exc})

        # Now, let's consider any subdirectories we may have...
        subdirs = []
        for dname in dirnames:
            # Skip it if it does not have __init__.py
            if not os.path.exists(os.path.join(dirpath, dname, '__init__.py')):
                continue

            # If it has extension(), delegate...
            ext_name = "%s%s.%s.extension" % (package, relpkg, dname)
            try:
                ext = importutils.import_class(ext_name)
            except ImportError:
                # extension() doesn't exist on it, so we'll explore
                # the directory for ourselves
                subdirs.append(dname)
            else:
                try:
                    ext(ext_mgr)
                except Exception as exc:
                    logger.warn(_('Failed to load extension %(ext_name)s:'
                                  '%(exc)s'),
                                {'ext_name': ext_name, 'exc': exc})

        # Update the list of directories we'll explore...
        dirnames[:] = subdirs


def core_authorizer(api_name, extension_name):
    """
    api_name = compute
    extension_name = admin_actions:suspend
    """
    def authorize(context, target=None, action=None):
        """
        ======================================================================================
        context = <nova.context.RequestContext object at 0x6dcf050>
        target = None
        action = None
        ======================================================================================
        """
        if target is None:
            target = {'project_id': context.project_id,
                      'user_id': context.user_id}
        if action is None:
            act = '%s:%s' % (api_name, extension_name)
        else:
            act = '%s:%s:%s' % (api_name, extension_name, action)
        
        """
        ======================================================================================
        context = <nova.context.RequestContext object at 0x6dcf050>
        target = {'project_id': u'4537aca4a4a4462fa4c59ad5b5581f00', 'user_id': u'91d732b65831491d8bd952b3111e62dd'}
        act = compute_extension:admin_actions:suspend
        ======================================================================================
        """
        xdrs.policy.enforce(context, act, target)
    return authorize


def extension_authorizer(api_name, extension_name):
    """
    ======================================================================================
    api_name = compute
    extension_name = admin_actions:suspend
    ======================================================================================
    """
    return core_authorizer('%s_extension' % api_name, extension_name)


def soft_extension_authorizer(api_name, extension_name):
    hard_authorize = extension_authorizer(api_name, extension_name)

    def authorize(context, action=None):
        try:
            hard_authorize(context, action=action)
            return True
        except exception.NotAuthorized:
            return False
    return authorize


def check_compute_policy(context, action, target, scope='compute'):
    _action = '%s:%s' % (scope, action)
    xdrs.policy.enforce(context, _action, target)


def expected_errors(errors):
    """
    Decorator for v3 API methods which specifies expected exceptions.

    Specify which exceptions may occur when an API method is called. If an
    unexpected exception occurs then return a 500 instead and ask the user
    of the API to file a bug report.
    """
    def decorator(f):
        @functools.wraps(f)
        def wrapped(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except Exception as exc:
                if isinstance(exc, webob.exc.WSGIHTTPException):
                    if isinstance(errors, int):
                        t_errors = (errors,)
                    else:
                        t_errors = errors
                    if exc.code in t_errors:
                        raise
                elif isinstance(exc, exception.PolicyNotAuthorized):
                    # Note(cyeoh): Special case to handle
                    # PolicyNotAuthorized exceptions so every
                    # extension method does not need to wrap authorize
                    # calls. ResourceExceptionHandler silently
                    # converts NotAuthorized to HTTPForbidden
                    raise
                elif isinstance(exc, exception.ValidationError):
                    # Note(oomichi): Handle a validation error, which
                    # happens due to invalid API parameters, as an
                    # expected error.
                    raise

                LOG.exception(_("Unexpected exception in API method"))
                raise webob.exc.HTTPInternalServerError()

        return wrapped

    return decorator
