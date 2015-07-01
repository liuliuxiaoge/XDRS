"""Utility methods for working with WSGI servers."""

from __future__ import print_function

import os.path
import socket
import sys

import eventlet.wsgi
import greenlet
from oslo.config import cfg
from paste import deploy
import routes.middleware
import ssl
import webob.dec
import webob.exc

from xdrs import exception
from xdrs.openstack.common import excutils
from xdrs.openstack.common.gettextutils import _
from xdrs.openstack.common import log as logging


CONF = cfg.CONF
CONF.import_opt('wsgi_default_pool_size', 'xdrs.service')
CONF.import_opt('max_header_line', 'xdrs.service')
CONF.import_opt('ssl_ca_file', 'xdrs.service')
CONF.import_opt('ssl_cert_file', 'xdrs.service')
CONF.import_opt('ssl_key_file', 'xdrs.service')
CONF.import_opt('tcp_keepidle', 'xdrs.service')
CONF.import_opt('wsgi_log_format', 'xdrs.service')
CONF.import_opt('api_paste_config', 'xdrs.service')

LOG = logging.getLogger(__name__)


class Server(object):
    """
    Server class to manage a WSGI server, serving a WSGI application.
    管理一个WSGI服务；
    """

    default_pool_size = CONF.wsgi_default_pool_size


    def __init__(self, name, app, host='0.0.0.0', port=0, pool_size=None,
                       protocol=eventlet.wsgi.HttpProtocol, backlog=128,
                       use_ssl=False, max_url_len=None):
        """
        Initialize, but do not start, a WSGI server.
        初始化但并不启动一个WSGI服务；
        """
        # Allow operators to customize http requests max header line size.
        eventlet.wsgi.MAX_HEADER_LINE = CONF.max_header_line
        self.name = name
        self.app = app
        self._server = None
        self._protocol = protocol
        self._pool = eventlet.GreenPool(pool_size or self.default_pool_size)
        
        self._logger = logging.getLogger("xdrs.%s.wsgi.server" % self.name)
        self._wsgi_logger = logging.WritableLogger(self._logger)
        
        self._use_ssl = use_ssl
        self._max_url_len = max_url_len

        if backlog < 1:
            raise exception.InvalidInput(
                    reason='The backlog must be more than 1')

        bind_addr = (host, port)
        # TODO(dims): eventlet's green dns/socket module does not actually
        # support IPv6 in getaddrinfo(). We need to get around this in the
        # future or monitor upstream for a fix
        try:
            info = socket.getaddrinfo(bind_addr[0],
                                      bind_addr[1],
                                      socket.AF_UNSPEC,
                                      socket.SOCK_STREAM)[0]
            family = info[0]
            bind_addr = info[-1]
        except Exception:
            family = socket.AF_INET

        try:
            self._socket = eventlet.listen(bind_addr, family, backlog=backlog)
        except EnvironmentError:
            LOG.error(_("Could not bind to %(host)s:%(port)s"),
                      {'host': host, 'port': port})
            raise

        (self.host, self.port) = self._socket.getsockname()[0:2]
        LOG.info(_("%(name)s listening on %(host)s:%(port)s") % self.__dict__)


    def start(self):
        """
        Start serving a WSGI application.
        启动一个WSGI服务；
        """
        if self._use_ssl:
            try:
                ca_file = CONF.ssl_ca_file
                cert_file = CONF.ssl_cert_file
                key_file = CONF.ssl_key_file

                if cert_file and not os.path.exists(cert_file):
                    raise RuntimeError(
                          _("Unable to find cert_file : %s") % cert_file)

                if ca_file and not os.path.exists(ca_file):
                    raise RuntimeError(
                          _("Unable to find ca_file : %s") % ca_file)

                if key_file and not os.path.exists(key_file):
                    raise RuntimeError(
                          _("Unable to find key_file : %s") % key_file)

                if self._use_ssl and (not cert_file or not key_file):
                    raise RuntimeError(
                          _("When running server in SSL mode, you must "
                            "specify both a cert_file and key_file "
                            "option value in your configuration file"))
                
                ssl_kwargs = {
                    'server_side': True,
                    'certfile': cert_file,
                    'keyfile': key_file,
                    'cert_reqs': ssl.CERT_NONE,
                }

                if CONF.ssl_ca_file:
                    ssl_kwargs['ca_certs'] = ca_file
                    ssl_kwargs['cert_reqs'] = ssl.CERT_REQUIRED

                self._socket = eventlet.wrap_ssl(self._socket,
                                                 **ssl_kwargs)

                self._socket.setsockopt(socket.SOL_SOCKET,
                                        socket.SO_REUSEADDR, 1)
                # sockets can hang around forever without keepalive
                self._socket.setsockopt(socket.SOL_SOCKET,
                                        socket.SO_KEEPALIVE, 1)

                # This option isn't available in the OS X version of eventlet
                if hasattr(socket, 'TCP_KEEPIDLE'):
                    self._socket.setsockopt(socket.IPPROTO_TCP,
                                    socket.TCP_KEEPIDLE,
                                    CONF.tcp_keepidle)

            except Exception:
                with excutils.save_and_reraise_exception():
                    LOG.error(_("Failed to start %(name)s on %(host)s"
                                ":%(port)s with SSL support") % self.__dict__)

        wsgi_kwargs = {
            'func': eventlet.wsgi.server,
            'sock': self._socket,
            'site': self.app,
            'protocol': self._protocol,
            'custom_pool': self._pool,
            'log': self._wsgi_logger,
            'log_format': CONF.wsgi_log_format,
            'debug': False
            }

        if self._max_url_len:
            wsgi_kwargs['url_length_limit'] = self._max_url_len

        self._server = eventlet.spawn(**wsgi_kwargs)


    def stop(self):
        """
        Stop this server.
        """
        LOG.info(_("Stopping WSGI server."))

        if self._server is not None:
            # Resize pool to stop new requests from being processed
            self._pool.resize(0)
            self._server.kill()


    def wait(self):
        """
        Block, until the server has stopped.
        """
        try:
            if self._server is not None:
                self._server.wait()
        except greenlet.GreenletExit:
            LOG.info(_("WSGI server has stopped."))


class Request(webob.Request):
    pass


class Application(object):
    """
    Base WSGI application wrapper. Subclasses need to implement __call__.
    """

    @classmethod
    def factory(cls, global_config, **local_config):
        """
        Used for paste app factories in paste.deploy config files.
        """
        return cls(**local_config)

    def __call__(self, environ, start_response):
        r"""
        Subclasses will probably want to implement __call__ like this:
        """
        raise NotImplementedError(_('You must implement __call__'))


class Middleware(Application):
    """
    Base WSGI middleware.
    """

    @classmethod
    def factory(cls, global_config, **local_config):
        """
        Used for paste app factories in paste.deploy config files.
        """
        def _factory(app):
            return cls(app, **local_config)
        return _factory

    def __init__(self, application):
        self.application = application

    def process_request(self, req):
        """
        Called on each request.
        """
        return None

    def process_response(self, response):
        """
        Do whatever you'd like to the response.
        """
        return response

    @webob.dec.wsgify(RequestClass=Request)
    def __call__(self, req):
        response = self.process_request(req)
        if response:
            return response
        response = req.get_response(self.application)
        return self.process_response(response)


class Debug(Middleware):
    """
    Helper class for debugging a WSGI application.
    """

    @webob.dec.wsgify(RequestClass=Request)
    def __call__(self, req):
        print(('*' * 40) + ' REQUEST ENVIRON')
        for key, value in req.environ.items():
            print(key, '=', value)
        print()
        resp = req.get_response(self.application)

        print(('*' * 40) + ' RESPONSE HEADERS')
        for (key, value) in resp.headers.iteritems():
            print(key, '=', value)
        print()

        resp.app_iter = self.print_generator(resp.app_iter)

        return resp

    @staticmethod
    def print_generator(app_iter):
        """
        Iterator that prints the contents of a wrapper string.
        """
        print(('*' * 40) + ' BODY')
        for part in app_iter:
            sys.stdout.write(part)
            sys.stdout.flush()
            yield part
        print()



class Router(object):
    """
    WSGI middleware that maps incoming requests to WSGI apps.
    """

    def __init__(self, mapper):
        """
        Create a router for the given routes.Mapper.
        """
        self.map = mapper
        self._router = routes.middleware.RoutesMiddleware(self._dispatch,
                                                          self.map)

    @webob.dec.wsgify(RequestClass=Request)
    def __call__(self, req):
        """
        Route the incoming request to a controller based on self.map.
        """
        return self._router


    @staticmethod
    @webob.dec.wsgify(RequestClass=Request)
    def _dispatch(req):
        """
        Dispatch the request to the appropriate controller.
        """
        match = req.environ['wsgiorg.routing_args'][1]
        if not match:
            return webob.exc.HTTPNotFound()
        app = match['controller']
        return app


class Loader(object):
    """
    Used to load WSGI applications from paste configurations.
    用于通过解析配置文件从paste文件中加载WSGI服务；
    """

    def __init__(self, config_path=None):
        """
        Initialize the loader, and attempt to find the config.
        """
        self.config_path = None

        config_path = config_path or CONF.api_paste_config
        if not os.path.isabs(config_path):
            self.config_path = CONF.find_file(config_path)
        elif os.path.exists(config_path):
            self.config_path = config_path

        if not self.config_path:
            raise exception.ConfigNotFound(path=config_path)


    def load_app(self, name):
        """
        Return the paste URLMap wrapped WSGI application.
        """
        try:
            LOG.debug(_("Loading app %(name)s from %(path)s") %
                      {'name': name, 'path': self.config_path})
            return deploy.loadapp("config:%s" % self.config_path, name=name)
        except LookupError as err:
            LOG.error(err)
            raise exception.PasteAppNotFound(name=name, path=self.config_path)