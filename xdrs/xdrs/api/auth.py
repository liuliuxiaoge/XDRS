"""
Common Auth Middleware.
++++通用身份验证的中间件，用于访问keystone实现身份验证操作；
"""

from oslo.config import cfg
import webob.dec
import webob.exc

from xdrs import context
from xdrs.openstack.common.gettextutils import _
from xdrs.openstack.common import jsonutils
from xdrs.openstack.common import log as logging
from xdrs import wsgi


auth_opts = [
    cfg.BoolOpt('api_rate_limit',
                default=False,
                help=('Whether to use per-user rate limiting for the api. '
                      'This option is only used by v2 api. Rate limiting '
                      'is removed from v3 api.')),
    # 不限制API访问频率，打开之后API的并发访问数量会受到限制，
    # 可以根据云平台的访问量及API进程的数量和承受能力来判断是否需要打开，
    # 如果关闭该选项，则大并发情况下API请求处理时间会比较久。
    
    cfg.StrOpt('auth_strategy',
               default='noauth',
               help='The strategy to use for auth: noauth or keystone.'),
    cfg.BoolOpt('use_forwarded_for',
                default=False,
                help='Treat X-Forwarded-For as the canonical remote address. '
                     'Only enable this if you have a sanitizing proxy.'),
]


CONF = cfg.CONF
CONF.register_opts(auth_opts)


LOG = logging.getLogger(__name__)


def _load_pipeline(loader, pipeline):
    filters = [loader.get_filter(n) for n in pipeline[:-1]]
    app = loader.get_app(pipeline[-1])
    filters.reverse()
    for filter in filters:
        app = filter(app)
    return app


def pipeline_factory(loader, global_conf, **local_conf):
    """A paste pipeline replica that keys off of auth_strategy."""
    pipeline = local_conf[CONF.auth_strategy]
    if not CONF.api_rate_limit:
        limit_name = CONF.auth_strategy + '_nolimit'
        pipeline = local_conf.get(limit_name, pipeline)
    pipeline = pipeline.split()
    # NOTE (Alex Xu): This is just for configuration file compatibility.
    # If the configuration file still contains 'ratelimit_v3', just ignore it.
    # We will remove this code at next release (J)
    if 'ratelimit_v3' in pipeline:
        LOG.warn(_('ratelimit_v3 is removed from v3 api.'))
        pipeline.remove('ratelimit_v3')
    return _load_pipeline(loader, pipeline)


class InjectContext(wsgi.Middleware):
    """Add a 'xdrs.context' to WSGI environ."""

    def __init__(self, context, *args, **kwargs):
        self.context = context
        super(InjectContext, self).__init__(*args, **kwargs)

    @webob.dec.wsgify(RequestClass=wsgi.Request)
    def __call__(self, req):
        req.environ['xdrs.context'] = self.context
        return self.application



class XdrsKeystoneContext(wsgi.Middleware):
    """
    Make a request context from keystone headers.
    从keystone头文件中形成request上下文信息；
    """

    @webob.dec.wsgify(RequestClass=wsgi.Request)
    def __call__(self, req):
        user_id = req.headers.get('X_USER')
        user_id = req.headers.get('X_USER_ID', user_id)
        if user_id is None:
            LOG.debug("Neither X_USER_ID nor X_USER found in request")
            return webob.exc.HTTPUnauthorized()

        roles = self._get_roles(req)

        if 'X_TENANT_ID' in req.headers:
            # This is the new header since Keystone went to ID/Name
            project_id = req.headers['X_TENANT_ID']
        else:
            # This is for legacy compatibility
            project_id = req.headers['X_TENANT']
        project_name = req.headers.get('X_TENANT_NAME')
        user_name = req.headers.get('X_USER_NAME')

        # Get the auth token
        auth_token = req.headers.get('X_AUTH_TOKEN',
                                     req.headers.get('X_STORAGE_TOKEN'))

        # Build a context, including the auth_token...
        remote_address = req.remote_addr
        if CONF.use_forwarded_for:
            remote_address = req.headers.get('X-Forwarded-For', remote_address)

        service_catalog = None
        if req.headers.get('X_SERVICE_CATALOG') is not None:
            try:
                catalog_header = req.headers.get('X_SERVICE_CATALOG')
                service_catalog = jsonutils.loads(catalog_header)
            except ValueError:
                raise webob.exc.HTTPInternalServerError(
                          _('Invalid service catalog json.'))

        ctx = context.RequestContext(user_id,
                                     project_id,
                                     user_name=user_name,
                                     project_name=project_name,
                                     roles=roles,
                                     auth_token=auth_token,
                                     remote_address=remote_address,
                                     service_catalog=service_catalog)

        req.environ['xdrs.context'] = ctx
        return self.application


    def _get_roles(self, req):
        """
        Get the list of roles.
        """

        if 'X_ROLES' in req.headers:
            roles = req.headers.get('X_ROLES', '')
        else:
            # Fallback to deprecated role header:
            roles = req.headers.get('X_ROLE', '')
            if roles:
                LOG.warn(_("Sourcing roles from deprecated X-Role HTTP "
                           "header"))
        return [r.strip() for r in roles.split(',')]
