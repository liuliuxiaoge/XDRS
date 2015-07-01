"""
Generic Node base class for all workers that run on hosts.
"""

import os
import random
import sys

from oslo.config import cfg
from oslo import messaging

from xdrs import baserpc
from xdrs import conductor
from xdrs import context
from xdrs import debugger
from xdrs import exception
from xdrs.objects import base as objects_base
from xdrs.openstack.common.gettextutils import _
from xdrs.openstack.common import importutils
from xdrs.openstack.common import log as logging
from xdrs.openstack.common import service
from xdrs import rpc
from xdrs import utils
from xdrs import version
from xdrs import wsgi

LOG = logging.getLogger(__name__)

"""
已经过分析；
"""
service_opts = [
    cfg.IntOpt('report_interval',
               default=10,
               help='Seconds between nodes reporting state to datastore'),
    cfg.BoolOpt('periodic_enable',
               default=True,
               help='Enable periodic tasks'),
    cfg.IntOpt('periodic_fuzzy_delay',
               default=60,
               help='Range of seconds to randomly delay when starting the'
                    ' periodic task scheduler to reduce stampeding.'
                    ' (Disable by setting to 0)'),
    cfg.StrOpt('osapi_xdrs_listen',
                default="0.0.0.0",
                help='The IP address on which the OpenStack API will listen.'),
    cfg.IntOpt('osapi_xdrs_listen_port',
               default=8778,
               help='The port on which the OpenStack API will listen.'),
    cfg.IntOpt('osapi_xdrs_workers',
               help='Number of workers for OpenStack API service. The default '
                    'will be the number of CPUs available.'),
    cfg.IntOpt('service_down_time',
               default=60,
               help='Maximum time since last check-in for up service'),
    
    
    cfg.StrOpt('host_manager',
               default='xdrs.hosts.manager.HostsManager',
               help='Full class name for the Manager for hosts'),
    cfg.StrOpt('vm_manager',
               default='xdrs.hosts.vms.VmsManager',
               help='Full class name for the Manager for vms'),
    cfg.StrOpt('xdrs_conductor',
               default='xdrs.conductor.manager.ConductorManager',
               help='Full class name for the Manager for vms'),
    cfg.StrOpt('xdrs_controller',
               default='xdrs.controller.manager.ControllerManager',
               help='Full class name for the Manager for vms'),
    cfg.StrOpt('xdrs_data_collection',
               default='xdrs.hosts.manager.DataCollectionManager',
               help='Full class name for the Manager for vms'),
    cfg.StrOpt('xdrs_load_detection',
               default='xdrs.hosts.manager.LoadDetectionManager',
               help='Full class name for the Manager for vms'),
    cfg.StrOpt('xdrs_vms_migration',
               default='xdrs.hosts.manager.VmsMigrationManager',
               help='Full class name for the Manager for vms'),
    cfg.StrOpt('xdrs_vms_selection',
               default='xdrs.hosts.manager.VmsSelectionManager',
               help='Full class name for the Manager for vms'),
    
    #"""
    #将所有配置参数集中放置在这里，用的时候导入即可；
    #"""
    cfg.StrOpt('local_data_directory',
                default="/var/lib/xdrs"),
    cfg.IntOpt('data_collector_data_length',
               default=100),
    cfg.StrOpt('host_cpu_overload_threshold',
               default=0.8),
    cfg.StrOpt('host_cpu_usable_by_vms',
               default=1.0),
    cfg.IntOpt('data_collector_interval',
               default=300),
    cfg.IntOpt('network_migration_bandwidth',
               default=10),
    cfg.StrOpt('underload_algorithm_path',
               default="xdrs.algorithms.underload_algorithm"),
    cfg.StrOpt('overload_algorithm_path',
               default="xdrs.algorithms.overload_algorithm"),
    cfg.StrOpt('vm_select_algorithm_path',
               default="xdrs.algorithms.vm_select_algorithm"),
    cfg.StrOpt('filter_scheduler_algorithm_path',
               default="xdrs.scheduler.filter_scheduler"),
    cfg.StrOpt('host_scheduler_algorithm_path',
               default="xdrs.scheduler.host_scheduler"),
             
       
    cfg.StrOpt('sleep_command',
               default="pm-suspend"),
    cfg.StrOpt('conductor_topic',
               default="xdrs_conductor"),
    cfg.StrOpt('controller_topic',
               default='xdrs_controller'),
    cfg.StrOpt('host_topic',
               default='xdrs_host'),
    cfg.StrOpt('vm_topic',
               default='xdrs_vm'),
    cfg.StrOpt('data_collection_topic',
               default='xdrs_data_collection'),
    cfg.StrOpt('load_detection_topic',
               default='xdrs_load_detection'),
    cfg.StrOpt('vms_selection_topic',
               default='xdrs_vms_selection'),
    cfg.StrOpt('vms_migration_topic',
               default='xdrs_vms_migration'),
    cfg.StrOpt('wait_time',
               default='1200000'),
    
    
    cfg.IntOpt('osapi_max_request_body_size',
               default=114688),
    cfg.BoolOpt('api_rate_limit',
                default=False),
    cfg.StrOpt('auth_strategy',
               default='noauth'),
    cfg.BoolOpt('use_forwarded_for',
                default=False),
    
    cfg.StrOpt('nova_catalog_info',
               default='compute:nova:publicURL'),
    cfg.StrOpt('nova_catalog_admin_info',
               default='compute:nova:adminURL'),
    cfg.StrOpt('nova_endpoint_template',
               default=None),
    cfg.StrOpt('nova_endpoint_admin_template',
               default=None),
    cfg.StrOpt('os_region_name',
               default=None),
    cfg.StrOpt('nova_ca_certificates_file',
               default=None),
    cfg.BoolOpt('nova_api_insecure',
                default=False),
                
    cfg.StrOpt('db_driver',
               default='xdrs.db'),
    
    cfg.BoolOpt('run_external_periodic_tasks',
                default=True),
    
    cfg.BoolOpt('fatal_exception_format_errors',
                default=False),
    
    cfg.BoolOpt('notify_api_faults', default=False),
    cfg.StrOpt('default_notification_level',
               default='INFO'),
    cfg.StrOpt('default_publisher_id',
               help='Default publisher_id for outgoing notifications'),
    
    cfg.StrOpt('pybasedir',
               default=os.path.abspath(os.path.join(os.path.dirname(__file__),                                               '../'))),
    cfg.StrOpt('bindir',
               default=os.path.join(sys.prefix, 'local', 'bin')),
    cfg.StrOpt('state_path',
               default='$pybasedir'),
    
    cfg.StrOpt('policy_file',
               default='policy.json',
               help=_('JSON file representing policy')),
    cfg.StrOpt('policy_default_rule',
               default='default',
               help=_('Rule checked when requested rule is not found')),
                
    cfg.BoolOpt('monkey_patch',
                default=False,
                help='Whether to log monkey patching'),
    cfg.ListOpt('monkey_patch_modules',
                default=[
                  'nova.api.ec2.cloud:%s' % (notify_decorator),
                  'nova.compute.api:%s' % (notify_decorator)
                  ],
                help='List of modules/decorators to monkey patch'),
    cfg.IntOpt('password_length',
               default=12,
               help='Length of generated instance admin passwords'),
    cfg.StrOpt('instance_usage_audit_period',
               default='month',
               help='Time period to generate instance usages for.  '
                    'Time period must be hour, day, month or year'),
    
    cfg.StrOpt('wsgi_log_format',
            default='%(client_ip)s "%(request_line)s" status: %(status_code)s'
                    ' len: %(body_length)s time: %(wall_seconds).7f',
            help='A python format string that is used as the template to '
                 'generate log lines. The following values can be formatted '
                 'into it: client_ip, date_time, request_line, status_code, '
                 'body_length, wall_seconds.'),
    cfg.StrOpt('ssl_ca_file',
               help="CA certificate file to use to verify "
                    "connecting clients"),
    cfg.StrOpt('ssl_cert_file',
               help="SSL certificate of API server"),
    cfg.StrOpt('ssl_key_file',
               help="SSL private key of API server"),
    cfg.IntOpt('tcp_keepidle',
               default=600,
               help="Sets the value of TCP_KEEPIDLE in seconds for each "
                    "server socket. Not supported on OS X."),
    cfg.IntOpt('wsgi_default_pool_size',
               default=1000,
               help="Size of the pool of greenthreads used by wsgi"),
    cfg.IntOpt('max_header_line',
               default=16384,
               help="Maximum line size of message headers to be accepted. "
                    "max_header_line may need to be increased when using "
                    "large tokens (typically those generated by the "
                    "Keystone v3 API with big service catalogs)."),
    
    cfg.MultiStrOpt('osapi_compute_extension',
                    default=[
                      'xdrs.api.openstack.compute.contrib.standard_extensions'
                      ],
                    help='osapi compute extension to load'),
    
    cfg.StrOpt('database.slave_connection',
               secret=True,
               help='The SQLAlchemy connection string used to connect to the '
                    'slave database'),
    
    cfg.StrOpt('remote_debug.host',
                help='Debug host (IP or name) to connect. Note '
                        'that using the remote debug option changes how '
                        'Nova uses the eventlet library to support async IO. '
                        'This could result in failures that do not occur '
                        'under normal operation. Use at your own risk.'),

    cfg.IntOpt('remote_debug.port',
                help='Debug port to connect. Note '
                        'that using the remote debug option changes how '
                        'Nova uses the eventlet library to support async IO. '
                        'This could result in failures that do not occur '
                        'under normal operation. Use at your own risk.'),
    
    cfg.StrOpt('api_paste_config',
               default="api-paste.ini",
               help='File name for the paste.deploy config for nova-api'),
    
    ]

CONF = cfg.CONF
CONF.register_opts(service_opts)

class Service(service.Service):
    """
    Service object for binaries running on hosts.

    A service takes a manager and enables rpc by listening to queues based
    on topic. It also periodically runs tasks on the manager and reports
    it state to the database services table.
    """
    def __init__(self, host, binary, topic, manager, report_interval=None,
                 periodic_enable=None, periodic_fuzzy_delay=None,
                 periodic_interval_max=None, db_allowed=True,
                 *args, **kwargs):
        super(Service, self).__init__()
        self.host = host
        self.binary = binary
        self.topic = topic
        self.manager_class_name = manager
        manager_class = importutils.import_class(self.manager_class_name)
        self.manager = manager_class(host=self.host, *args, **kwargs)
        self.rpcserver = None
        self.report_interval = report_interval
        self.periodic_enable = periodic_enable
        self.periodic_fuzzy_delay = periodic_fuzzy_delay
        self.periodic_interval_max = periodic_interval_max
        self.saved_args, self.saved_kwargs = args, kwargs
        self.backdoor_port = None
        """
        conductor.API需要进行进一步实现；
        """
        self.conductor_api = conductor.API(use_local=db_allowed)
        self.conductor_api.wait_until_ready(context.get_admin_context())
        
        """
        ======================================================================================
        self.host = node01.shinian.com
        self.binary = nova-scheduler
        self.topic = scheduler
        self.manager_class_name = nova.scheduler.manager.SchedulerManager
        self.manager = <nova.scheduler.manager.SchedulerManager object at 0x3895c10>
        self.rpcserver = None
        self.report_interval = 10
        self.periodic_enable = True
        self.periodic_fuzzy_delay = 60
        self.periodic_interval_max = None
        self.saved_args = ()
        self.saved_kwargs = {}
        self.backdoor_port = None
        self.conductor_api = <nova.conductor.api.LocalAPI object at 0x3910a90>
        ======================================================================================
        """

    def start(self):
        verstr = version.version_string_with_package()
        LOG.audit(_('Starting %(topic)s node (version %(version)s)'),
                  {'topic': self.topic, 'version': verstr})
        
        self.basic_config_check()
        
        """
        服务中的初始化操作；
        @@@@这里很重要；
        需要实现hosts/vms/scheduler中的init_host方法；
        """
        self.manager.init_host()
        """
        ======================================================================================
        self.manager = <nova.cert.manager.CertManager object at 0x3ed4550>
        self.manager.init_host = <bound method CertManager.init_host of <nova.cert.manager.CertManager object at 0x3ed4550>>
        ======================================================================================
        ======================================================================================
        self.manager = <nova.conductor.manager.ConductorManager object at 0x248f490>
        self.manager.init_host = <bound method ConductorManager.init_host of <nova.conductor.manager.ConductorManager object at 0x248f490>>
        ======================================================================================
        ======================================================================================
        self.manager = <nova.scheduler.manager.SchedulerManager object at 0x369d490>
        self.manager.init_host = <bound method SchedulerManager.init_host of <nova.scheduler.manager.SchedulerManager object at 0x369d490>>
        ======================================================================================
        ======================================================================================
        self.manager = <nova.compute.manager.ComputeManager object at 0x2beba90>
        self.manager.init_host = <bound method ComputeManager.init_host of <nova.compute.manager.ComputeManager object at 0x2beba90>>
        ======================================================================================
        ======================================================================================
        self.manager = <nova.console.manager.ConsoleProxyManager object at 0x2898490>
        self.manager.init_host = <bound method ConsoleProxyManager.init_host of <nova.console.manager.ConsoleProxyManager object at 0x2898490>>
        ======================================================================================
        """
        
        self.model_disconnected = False
        ctxt = context.get_admin_context()
        
        try:
            self.service_ref = self.conductor_api.service_get_by_args(ctxt,
                    self.host, self.binary)
            self.service_id = self.service_ref['id']
            """
            ======================================================================================
            ctxt = <nova.context.RequestContext object at 0x1f996d0>
            self.host = node01.shinian.com
            self.binary = nova-scheduler
            self.service_ref = {'binary': u'nova-scheduler', 'deleted': 0L, 'created_at': '2015-01-08T02:46:44.000000', 'updated_at': '2015-01-30T09:29:40.000000', 'report_count': 192315L, 'topic': u'scheduler', 'host': u'node01.shinian.com', 'disabled': False, 'deleted_at': None, 'disabled_reason': None, 'id': 2L}
            self.service_id = 2
            ======================================================================================
            """
            
        except exception.NotFound:
            try:
                self.service_ref = self._create_service_ref(ctxt)
            except (exception.ServiceTopicExists,
                    exception.ServiceBinaryExists):
                # NOTE(danms): If we race to create a record with a sibling
                # worker, don't fail here.
                self.service_ref = self.conductor_api.service_get_by_args(ctxt,
                    self.host, self.binary)


        """
        在计算服务初始化之后，且在计算服务完全应用之前，务必要确认更新
        可用的资源信息；
        @@@@这里很重要；
        需要在hosts和vms中实现这个方法，同上面的init_host方法，还未解决；
        """
        self.manager.pre_start_hook()


        """
        RPC机制的应用；
        @@@@这里很重要；
        """
        if self.backdoor_port is not None:
            self.manager.backdoor_port = self.backdoor_port
        LOG.debug(_("Creating RPC server for service %s") % self.topic)
        target = messaging.Target(topic=self.topic, server=self.host)
        """
        self.topic = scheduler
        self.host = node01.shinian.com
        target = <Target topic=scheduler, server=node01.shinian.com>
        """
        endpoints = [
            self.manager,
            baserpc.BaseRPCAPI(self.manager.service_name, self.backdoor_port)
        ]
        """
        ======================================================================================
        self.manager = <nova.scheduler.manager.SchedulerManager object at 0x2b71210>
        self.manager.service_name = scheduler
        self.backdoor_port = None
        endpoints = [<nova.scheduler.manager.SchedulerManager object at 0x2b71210>, <nova.baserpc.BaseRPCAPI object at 0x4e3ee10>]
        ======================================================================================
        """    
        endpoints.extend(self.manager.additional_endpoints)
        """
        ======================================================================================
        endpoints = [<nova.scheduler.manager.SchedulerManager object at 0x2e341d0>, 
                    <nova.baserpc.BaseRPCAPI object at 0x50aafd0>, 
                    <nova.scheduler.manager._SchedulerManagerV3Proxy object at 0x2e9df90>]
        ======================================================================================
        """
        """
        objects_base.XdrsObjectSerializer需要进行进一步实现，还未完成；
        """
        serializer = objects_base.XdrsObjectSerializer()
        self.rpcserver = rpc.get_server(target, endpoints, serializer)
        self.rpcserver.start()

        if self.periodic_enable:
            if self.periodic_fuzzy_delay:
                initial_delay = random.randint(0, self.periodic_fuzzy_delay)
            else:
                initial_delay = None

            """
            启动线程，周期性任务的实现；
            @@@@这里很重要；
            """
            self.tg.add_dynamic_timer(self.periodic_tasks,
                                     initial_delay=initial_delay,
                                     periodic_interval_max=
                                        self.periodic_interval_max)


    def _create_service_ref(self, context):
        svc_values = {
            'host': self.host,
            'binary': self.binary,
            'topic': self.topic,
            'report_count': 0
        }
        
        service = self.conductor_api.service_create(context, svc_values)
        self.service_id = service['id']
        return service

    def __getattr__(self, key):
        manager = self.__dict__.get('manager', None)
        return getattr(manager, key)


    @classmethod
    def create(cls, host=None, binary=None, topic=None, manager=None,
               report_interval=None, periodic_enable=None,
               periodic_fuzzy_delay=None, periodic_interval_max=None,
               db_allowed=True):
        """
        Instantiates class and passes back application object.
        """
        if not host:
            host = CONF.host
        if not binary:
            binary = os.path.basename(sys.argv[0])
        if not topic:
            topic = binary.rpartition('xdrs-')[2]
        if not manager:
            manager_cls = ('%s_manager' %
                           binary.rpartition('xdrs-')[2])
            manager = CONF.get(manager_cls, None)
        """
        ======================================================================================
        binary = xdrs_conductor
        topic = xdrs_conductor
        manager_cls = conductor_manager
        manager = xdrs.conductor.manager.ConductorManager
        
        binary = xdrs_controller
        topic = xdrs_controller
        manager_cls = controller_manager
        manager = xdrs.controller.manager.ControllerManager
        
        binary = xdrs_data_collection
        topic = xdrs_data_collection
        manager_cls = data_collection_manager
        manager = xdrs.hosts.manager.DataCollectionManager
        
        binary = xdrs_load_detection
        topic = xdrs_load_detection
        manager_cls = load_detection_manager
        manager = xdrs.hosts.manager.LoadDetectionManager
        
        binary = xdrs_vms_migration
        topic = xdrs_vms_migration
        manager_cls = vms_migration_manager
        manager = xdrs.hosts.manager.VmsMigrationManager
        
        binary = xdrs_vms_selection
        topic = xdrs_vms_selection
        manager_cls = vms_selection_manager
        manager = xdrs.hosts.manager.VmsSelectionManager
        
        binary = xdrs_host
        topic = xdrs_host
        manager_cls = host_manager
        manager = xdrs.hosts.manager.HostManager
        
        binary = xdrs_vm
        topic = xdrs_vm
        manager_cls = vm_manager
        manager = xdrs.vms.manager.VmManager
        ======================================================================================
        """
        if report_interval is None:
            report_interval = CONF.report_interval
        if periodic_enable is None:
            periodic_enable = CONF.periodic_enable
        if periodic_fuzzy_delay is None:
            periodic_fuzzy_delay = CONF.periodic_fuzzy_delay

        debugger.init()

        service_obj = cls(host, binary, topic, manager,
                          report_interval=report_interval,
                          periodic_enable=periodic_enable,
                          periodic_fuzzy_delay=periodic_fuzzy_delay,
                          periodic_interval_max=periodic_interval_max,
                          db_allowed=db_allowed)
        """
        ======================================================================================
        cls = <class 'nova.service.Service'>
        host = node01.shinian.com
        binary = nova-scheduler
        topic = scheduler
        manager = nova.scheduler.manager.SchedulerManager
        report_interval = 10
        periodic_enable = True
        periodic_fuzzy_delay = 60
        periodic_interval_max = None
        db_allowed = True
        ======================================================================================
        """

        return service_obj


    def kill(self):
        """
        Destroy the service object in the datastore.
        """
        self.stop()
        try:
            self.conductor_api.service_destroy(context.get_admin_context(),
                                               self.service_id)
        except exception.NotFound:
            LOG.warn(_('Service killed that has no database entry'))


    def stop(self):
        try:
            self.rpcserver.stop()
            self.rpcserver.wait()
        except Exception:
            pass

        super(Service, self).stop()

    """
    这里需要进行进一步的实现；
    """
    def periodic_tasks(self, raise_on_error=False):
        """Tasks to be run at a periodic interval."""
        ctxt = context.get_admin_context()
        return self.manager.periodic_tasks(ctxt, raise_on_error=raise_on_error)


    def basic_config_check(self):
        """Perform basic config checks before starting processing."""
        try:
            with utils.tempdir():
                pass
        except Exception as e:
            LOG.error(_('Temporary directory is invalid: %s'), e)
            sys.exit(1)


class WSGIService(object):
    """Provides ability to launch API from a 'paste' configuration."""
    
    def __init__(self, name, loader=None, use_ssl=False, max_url_len=None):
        """
        Initialize, but do not start the WSGI server.
        """
        self.name = name
        self.loader = loader or wsgi.Loader()
        self.app = self.loader.load_app(name)
        """
        self.loader.load_app = <bound method Loader.load_app of 
                                    <nova.wsgi.Loader object at 0x3216310>>
        """
        """
        ======================================================================================
        name = ec2
        self.app = {(None, '/services/Cloud'): <nova.api.ec2.FaultWrapper object at 0x3975990>}
        ======================================================================================
        name = osapi_compute
        self.app = {(None, '/v3'): <nova.api.openstack.FaultWrapper object at 0x42dfdd0>, 
                    (None, '/v1.1'): <nova.api.openstack.FaultWrapper object at 0x4adae10>, 
                    (None, '/v2'): <nova.api.openstack.FaultWrapper object at 0x42dca10>, 
                    (None, ''): <nova.api.openstack.FaultWrapper object at 0x42dfed0>}
        ======================================================================================
        name = metadata
        self.app = {(None, ''): <nova.api.ec2.FaultWrapper object at 0x4aee110>}
        ======================================================================================
        """
        
        self.host = getattr(CONF, '%s_listen' % name, "0.0.0.0")
        self.port = getattr(CONF, '%s_listen_port' % name, 0)
        self.workers = (getattr(CONF, '%s_workers' % name, None) or
                        utils.cpu_count())
        if self.workers and self.workers < 1:
            worker_name = '%s_workers' % name
            msg = (_("%(worker_name)s value of %(workers)s is invalid, "
                     "must be greater than 0") %
                   {'worker_name': worker_name,
                    'workers': str(self.workers)})
            raise exception.InvalidInput(msg)
        self.use_ssl = use_ssl
        self.server = wsgi.Server(name,
                                 self.app,
                                 host=self.host,
                                 port=self.port,
                                 use_ssl=self.use_ssl,
                                 max_url_len=max_url_len)
        """
        ======================================================================================
        name = ec2
        self.app = {(None, '/services/Cloud'): <nova.api.ec2.FaultWrapper object at 0x29b8ad0>}
        self.host = 0.0.0.0
        self.port = 8773
        self.use_ssl = False
        max_url_len = 16384
        ======================================================================================
        name = osapi_compute
        self.app = {(None, '/v3'): <nova.api.openstack.FaultWrapper object at 0x331cf10>, (None, '/v1.1'): <nova.api.openstack.FaultWrapper object at 0x3b150d0>, (None, '/v2'): <nova.api.openstack.FaultWrapper object at 0x3319b50>, (None, ''): <nova.api.openstack.FaultWrapper object at 0x331d050>}
        self.host = 0.0.0.0
        self.port = 8774
        self.use_ssl = False
        max_url_len = None
        ======================================================================================
        name = metadata
        self.app = {(None, ''): <nova.api.ec2.FaultWrapper object at 0x3b29250>}
        self.host = 0.0.0.0
        self.port = 8775
        self.use_ssl = False
        max_url_len = None
        ======================================================================================
        """
        self.backdoor_port = None


    def start(self):
        """
        Start serving this service using loaded configuration.
        @@@@注：在nova-compute中是需要应用到方法init_host/pre_start_hook/post_start_hook的，
        所以这里保留此源码，后续分析xdrs的host和vm部分是否需要此源码；
        """
        if self.manager:
            self.manager.init_host()
            if self.backdoor_port is not None:
                self.manager.backdoor_port = self.backdoor_port
        self.server.start()
        self.port = self.server.port


    def stop(self):
        """
        Stop serving this API.
        :returns: None
        """
        self.server.stop()


    def wait(self):
        """
        Wait for the service to stop serving this API.
        :returns: None
        """
        self.server.wait()


def process_launcher():
    return service.ProcessLauncher()


_launcher = None


def serve(server, workers=None):   
    global _launcher
    if _launcher:
        raise RuntimeError(_('serve() can only be called once'))

    _launcher = service.launch(server, workers=workers)


def wait():
    _launcher.wait()