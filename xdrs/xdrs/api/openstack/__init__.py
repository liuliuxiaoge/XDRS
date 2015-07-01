"""
OpenStack API控制器的WSGI中间件；
关于异常处理的中间件的实现类；
根据请求信息实现路由OpenStack API到匹配的控制器和方法上；
"""

from oslo.config import cfg
import routes
import stevedore
import webob.dec
import webob.exc

from xdrs.api.openstack import extensions
from xdrs.api.openstack import wsgi
from xdrs import exception
from xdrs import notifications
from xdrs.openstack.common import gettextutils
from xdrs.openstack.common.gettextutils import _
from xdrs.openstack.common import log as logging
from xdrs import utils
from xdrs import wsgi as base_wsgi

LOG = logging.getLogger(__name__)
CONF = cfg.CONF


class FaultWrapper(base_wsgi.Middleware):
    """
    关于异常处理的中间件的实现类；
    """

    _status_to_type = {}

    @staticmethod
    def status_to_type(status):
        if not FaultWrapper._status_to_type:
            for clazz in utils.walk_class_hierarchy(webob.exc.HTTPError):
                FaultWrapper._status_to_type[clazz.code] = clazz
        return FaultWrapper._status_to_type.get(
                                  status, webob.exc.HTTPInternalServerError)()

    def _error(self, inner, req):
        LOG.exception(_("Caught error: %s"), unicode(inner))

        safe = getattr(inner, 'safe', False)
        headers = getattr(inner, 'headers', None)
        status = getattr(inner, 'code', 500)
        if status is None:
            status = 500

        msg_dict = dict(url=req.url, status=status)
        LOG.info(_("%(url)s returned with HTTP %(status)d") % msg_dict)
        outer = self.status_to_type(status)
        if headers:
            outer.headers = headers
        # NOTE(johannes): We leave the explanation empty here on
        # purpose. It could possibly have sensitive information
        # that should not be returned back to the user. See
        # bugs 868360 and 874472
        # NOTE(eglynn): However, it would be over-conservative and
        # inconsistent with the EC2 API to hide every exception,
        # including those that are safe to expose, see bug 1021373
        if safe:
            if isinstance(inner.msg_fmt, gettextutils.Message):
                user_locale = req.best_match_language()
                inner_msg = gettextutils.translate(
                        inner.msg_fmt, user_locale)
            else:
                inner_msg = unicode(inner)
            outer.explanation = '%s: %s' % (inner.__class__.__name__,
                                            inner_msg)

        notifications.send_api_fault(req.url, status, inner)
        return wsgi.Fault(outer)

    @webob.dec.wsgify(RequestClass=wsgi.Request)
    def __call__(self, req):
        """
        @@@@注：
        在xdrs-api具体WSGI服务启动的过程中，只是搭好框架，在执行具体操作的过程中才会
        调用这里具体的方法，如nova list的输出如下：
        ======================================================================================
        req = GET /v2/4537aca4a4a4462fa4c59ad5b5581f00/servers/detail HTTP/1.0
        Accept: application/json
        Accept-Encoding: gzip, deflate, compress
        Content-Length: 0
        Content-Type: text/plain
        Host: 172.21.7.40:8774
        User-Agent: python-novaclient
        X-Auth-Project-Id: admin
        X-Auth-Token: MIIT9wYJKoZIhvcNAQcCoIIT6DCCE+QCAQExCTAHBgUrDgMCGjCCEk0GCSqGSIb3DQEHAaCCEj4EghI6eyJhY2Nlc3MiOiB7InRva2VuIjogeyJpc3N1ZWRfYXQiOiAiMjAxNS0wMy0yNVQwMjozMTozNy42MDQzNjMiLCAiZXhwaXJlcyI6ICIyMDE1LTAzLTI1VDAzOjMxOjM3WiIsICJpZCI6ICJwbGFjZWhvbGRlciIsICJ0ZW5hbnQiOiB7ImRlc2NyaXB0aW9uIjogImFkbWluIHRlbmFudCIsICJlbmFibGVkIjogdHJ1ZSwgImlkIjogIjQ1MzdhY2E0YTRhNDQ2MmZhNGM1OWFkNWI1NTgxZjAwIiwgIm5hbWUiOiAiYWRtaW4ifX0sICJzZXJ2aWNlQ2F0YWxvZyI6IFt7ImVuZHBvaW50cyI6IFt7ImFkbWluVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo4Nzc0L3YyLzQ1MzdhY2E0YTRhNDQ2MmZhNGM1OWFkNWI1NTgxZjAwIiwgInJlZ2lvbiI6ICJSZWdpb25PbmUiLCAiaW50ZXJuYWxVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjg3NzQvdjIvNDUzN2FjYTRhNGE0NDYyZmE0YzU5YWQ1YjU1ODFmMDAiLCAiaWQiOiAiMTZiMTVjYzVmZjUwNGNiODlmNTg2NjRlMjdhNjljNjkiLCAicHVibGljVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo4Nzc0L3YyLzQ1MzdhY2E0YTRhNDQ2MmZhNGM1OWFkNWI1NTgxZjAwIn1dLCAiZW5kcG9pbnRzX2xpbmtzIjogW10sICJ0eXBlIjogImNvbXB1dGUiLCAibmFtZSI6ICJub3ZhIn0sIHsiZW5kcG9pbnRzIjogW3siYWRtaW5VUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjk2OTYvIiwgInJlZ2lvbiI6ICJSZWdpb25PbmUiLCAiaW50ZXJuYWxVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjk2OTYvIiwgImlkIjogIjFiMjkzYTgxNjk2YjRiN2Y4OTZlYWQ0NjIyYTFjMmExIiwgInB1YmxpY1VSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6OTY5Ni8ifV0sICJlbmRwb2ludHNfbGlua3MiOiBbXSwgInR5cGUiOiAibmV0d29yayIsICJuYW1lIjogIm5ldXRyb24ifSwgeyJlbmRwb2ludHMiOiBbeyJhZG1pblVSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODc3Ni92Mi80NTM3YWNhNGE0YTQ0NjJmYTRjNTlhZDViNTU4MWYwMCIsICJyZWdpb24iOiAiUmVnaW9uT25lIiwgImludGVybmFsVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo4Nzc2L3YyLzQ1MzdhY2E0YTRhNDQ2MmZhNGM1OWFkNWI1NTgxZjAwIiwgImlkIjogIjNhNzY3OWNjZTdkZjRhY2ZhMTZiM2NhNTJkZGNmYzgyIiwgInB1YmxpY1VSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODc3Ni92Mi80NTM3YWNhNGE0YTQ0NjJmYTRjNTlhZDViNTU4MWYwMCJ9XSwgImVuZHBvaW50c19saW5rcyI6IFtdLCAidHlwZSI6ICJ2b2x1bWV2MiIsICJuYW1lIjogImNpbmRlcnYyIn0sIHsiZW5kcG9pbnRzIjogW3siYWRtaW5VUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjg3NzQvdjMiLCAicmVnaW9uIjogIlJlZ2lvbk9uZSIsICJpbnRlcm5hbFVSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODc3NC92MyIsICJpZCI6ICIwYmIxZDFiODhhZmU0MGRhOTNiY2IxNTg0Y2ExN2ZiOSIsICJwdWJsaWNVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjg3NzQvdjMifV0sICJlbmRwb2ludHNfbGlua3MiOiBbXSwgInR5cGUiOiAiY29tcHV0ZXYzIiwgIm5hbWUiOiAibm92YXYzIn0sIHsiZW5kcG9pbnRzIjogW3siYWRtaW5VUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjgwODAiLCAicmVnaW9uIjogIlJlZ2lvbk9uZSIsICJpbnRlcm5hbFVSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODA4MCIsICJpZCI6ICIxZTMyZTE3MmU3OWM0YzVhYTZiNWM3ZjhkNzVhZjRmYiIsICJwdWJsaWNVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjgwODAifV0sICJlbmRwb2ludHNfbGlua3MiOiBbXSwgInR5cGUiOiAiczMiLCAibmFtZSI6ICJzd2lmdF9zMyJ9LCB7ImVuZHBvaW50cyI6IFt7ImFkbWluVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo5MjkyIiwgInJlZ2lvbiI6ICJSZWdpb25PbmUiLCAiaW50ZXJuYWxVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjkyOTIiLCAiaWQiOiAiM2QxYzc5MjY1MWEwNDljNWE2MWUzNWJmZWZjNGM4OGIiLCAicHVibGljVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo5MjkyIn1dLCAiZW5kcG9pbnRzX2xpbmtzIjogW10sICJ0eXBlIjogImltYWdlIiwgIm5hbWUiOiAiZ2xhbmNlIn0sIHsiZW5kcG9pbnRzIjogW3siYWRtaW5VUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjg3NzciLCAicmVnaW9uIjogIlJlZ2lvbk9uZSIsICJpbnRlcm5hbFVSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODc3NyIsICJpZCI6ICIzOWE0YzA2NDIzYTg0OTNjOTI4ZGExOGY0YTVjY2MxZiIsICJwdWJsaWNVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjg3NzcifV0sICJlbmRwb2ludHNfbGlua3MiOiBbXSwgInR5cGUiOiAibWV0ZXJpbmciLCAibmFtZSI6ICJjZWlsb21ldGVyIn0sIHsiZW5kcG9pbnRzIjogW3siYWRtaW5VUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjgwMDAvdjEvIiwgInJlZ2lvbiI6ICJSZWdpb25PbmUiLCAiaW50ZXJuYWxVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjgwMDAvdjEvIiwgImlkIjogIjU1NzBiOGY4MTE0OTRlMWI5NTVkYjZlNTAzZGYyYWZkIiwgInB1YmxpY1VSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODAwMC92MS8ifV0sICJlbmRwb2ludHNfbGlua3MiOiBbXSwgInR5cGUiOiAiY2xvdWRmb3JtYXRpb24iLCAibmFtZSI6ICJoZWF0LWNmbiJ9LCB7ImVuZHBvaW50cyI6IFt7ImFkbWluVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo4Nzc2L3YxLzQ1MzdhY2E0YTRhNDQ2MmZhNGM1OWFkNWI1NTgxZjAwIiwgInJlZ2lvbiI6ICJSZWdpb25PbmUiLCAiaW50ZXJuYWxVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjg3NzYvdjEvNDUzN2FjYTRhNGE0NDYyZmE0YzU5YWQ1YjU1ODFmMDAiLCAiaWQiOiAiMGExYzhkYTRmMTU2NDk1YWFkMjEzMGUyYzA2OTE5ODIiLCAicHVibGljVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo4Nzc2L3YxLzQ1MzdhY2E0YTRhNDQ2MmZhNGM1OWFkNWI1NTgxZjAwIn1dLCAiZW5kcG9pbnRzX2xpbmtzIjogW10sICJ0eXBlIjogInZvbHVtZSIsICJuYW1lIjogImNpbmRlciJ9LCB7ImVuZHBvaW50cyI6IFt7ImFkbWluVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo4NzczL3NlcnZpY2VzL0FkbWluIiwgInJlZ2lvbiI6ICJSZWdpb25PbmUiLCAiaW50ZXJuYWxVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjg3NzMvc2VydmljZXMvQ2xvdWQiLCAiaWQiOiAiMDMzZjY3ZTk1MDBjNDljYThmOGIxODkzZTJhN2VkYWYiLCAicHVibGljVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo4NzczL3NlcnZpY2VzL0Nsb3VkIn1dLCAiZW5kcG9pbnRzX2xpbmtzIjogW10sICJ0eXBlIjogImVjMiIsICJuYW1lIjogIm5vdmFfZWMyIn0sIHsiZW5kcG9pbnRzIjogW3siYWRtaW5VUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjgwMDQvdjEvNDUzN2FjYTRhNGE0NDYyZmE0YzU5YWQ1YjU1ODFmMDAiLCAicmVnaW9uIjogIlJlZ2lvbk9uZSIsICJpbnRlcm5hbFVSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODAwNC92MS80NTM3YWNhNGE0YTQ0NjJmYTRjNTlhZDViNTU4MWYwMCIsICJpZCI6ICI0YmViNjQ0MjUzYWU0NzdmOWU5NDk2ZWVkZDEwOTNhNSIsICJwdWJsaWNVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjgwMDQvdjEvNDUzN2FjYTRhNGE0NDYyZmE0YzU5YWQ1YjU1ODFmMDAifV0sICJlbmRwb2ludHNfbGlua3MiOiBbXSwgInR5cGUiOiAib3JjaGVzdHJhdGlvbiIsICJuYW1lIjogImhlYXQifSwgeyJlbmRwb2ludHMiOiBbeyJhZG1pblVSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODA4MC8iLCAicmVnaW9uIjogIlJlZ2lvbk9uZSIsICJpbnRlcm5hbFVSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODA4MC92MS9BVVRIXzQ1MzdhY2E0YTRhNDQ2MmZhNGM1OWFkNWI1NTgxZjAwIiwgImlkIjogIjNhMTA2MzU0MjYxMDQzMjk5YTVkMjQ3ZTVmMjU5NGQyIiwgInB1YmxpY1VSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODA4MC92MS9BVVRIXzQ1MzdhY2E0YTRhNDQ2MmZhNGM1OWFkNWI1NTgxZjAwIn1dLCAiZW5kcG9pbnRzX2xpbmtzIjogW10sICJ0eXBlIjogIm9iamVjdC1zdG9yZSIsICJuYW1lIjogInN3aWZ0In0sIHsiZW5kcG9pbnRzIjogW3siYWRtaW5VUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjM1MzU3L3YyLjAiLCAicmVnaW9uIjogIlJlZ2lvbk9uZSIsICJpbnRlcm5hbFVSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6NTAwMC92Mi4wIiwgImlkIjogIjVjNGVlN2MzMTE4NDQyNGM5NDJhMWM1MjgxODU3MmZiIiwgInB1YmxpY1VSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6NTAwMC92Mi4wIn1dLCAiZW5kcG9pbnRzX2xpbmtzIjogW10sICJ0eXBlIjogImlkZW50aXR5IiwgIm5hbWUiOiAia2V5c3RvbmUifV0sICJ1c2VyIjogeyJ1c2VybmFtZSI6ICJhZG1pbiIsICJyb2xlc19saW5rcyI6IFtdLCAiaWQiOiAiOTFkNzMyYjY1ODMxNDkxZDhiZDk1MmIzMTExZTYyZGQiLCAicm9sZXMiOiBbeyJuYW1lIjogImhlYXRfc3RhY2tfb3duZXIifSwgeyJuYW1lIjogIl9tZW1iZXJfIn0sIHsibmFtZSI6ICJhZG1pbiJ9XSwgIm5hbWUiOiAiYWRtaW4ifSwgIm1ldGFkYXRhIjogeyJpc19hZG1pbiI6IDAsICJyb2xlcyI6IFsiZDlmZGVlODI1NjE3NGJlNWE3MmFjZGZmNDNkM2VkZDMiLCAiOWZlMmZmOWVlNDM4NGIxODk0YTkwODc4ZDNlOTJiYWIiLCAiN2E1ZTg5MmFiYTE5NDI3NWI3ZjQxZWM4Njg2ZDUwOGYiXX19fTGCAYEwggF9AgEBMFwwVzELMAkGA1UEBhMCVVMxDjAMBgNVBAgMBVVuc2V0MQ4wDAYDVQQHDAVVbnNldDEOMAwGA1UECgwFVW5zZXQxGDAWBgNVBAMMD3d3dy5leGFtcGxlLmNvbQIBATAHBgUrDgMCGjANBgkqhkiG9w0BAQEFAASCAQCGfvKOlil4SnYc2OfnYsTuglZg-oRqGqyhg95MlW2dc74rITI-KuoS5n+GUktnI01S1Gskvl1zq0Wf038xqi+55+dZmKWLqev2drqISk1dSi+qtl6BzeebsfaUtMMA+mfdZp6n6At-bpSNQQVpnWvYHVSeb68KDck6xtGn6kDb7fvX7A5SP+hurI9S+VNHLOE3UP5iox0ObmNl2NylDavSYs7zRkDy759K1uNAo3p6z7uWOKOaUcEow4Ooqf8UmLFGMeGGKdkZcYD3TUEXwEDGGQdrPYJGoxarMTD0a1+DIRZgxbBiS936FQHbnpr0LcFwsBDKcKWHDeAqOEZQmYmK
        self.application = <nova.api.sizelimit.RequestBodySizeLimiter object at 0x5086210>
        ======================================================================================
        """

        try:
            return req.get_response(self.application)
        except Exception as ex:
            return self._error(ex, req)


class APIMapper(routes.Mapper):
    def routematch(self, url=None, environ=None):
        if url == "":
            result = self._match("", environ)
            return result[0], result[1]
        return routes.Mapper.routematch(self, url, environ)

    def connect(self, *args, **kargs):
        # NOTE(vish): Default the format part of a route to only accept json
        #             and xml so it doesn't eat all characters after a '.'
        #             in the url.
        kargs.setdefault('requirements', {})
        if not kargs['requirements'].get('format'):
            kargs['requirements']['format'] = 'json|xml'
        return routes.Mapper.connect(self, *args, **kargs)


class ProjectMapper(APIMapper):
    def resource(self, member_name, collection_name, **kwargs):
        if 'parent_resource' not in kwargs:
            kwargs['path_prefix'] = '{project_id}/'
        else:
            parent_resource = kwargs['parent_resource']
            p_collection = parent_resource['collection_name']
            p_member = parent_resource['member_name']
            kwargs['path_prefix'] = '{project_id}/%s/:%s_id' % (p_collection,
                                                                p_member)
        
        """
        ======================================================================================
        member_name = console
        collection_name = consoles
        kwargs = {'parent_resource': {'collection_name': 'servers', 
                                     'member_name': 'server'}, 
                  'controller': <nova.api.openstack.wsgi.Resource object at 0x32c2950>, 
                  'path_prefix': '{project_id}/servers/:server_id'}
        ======================================================================================
        """
        routes.Mapper.resource(self, member_name,
                                     collection_name,
                                     **kwargs)


class PlainMapper(APIMapper):
    def resource(self, member_name, collection_name, **kwargs):
        if 'parent_resource' in kwargs:
            parent_resource = kwargs['parent_resource']
            p_collection = parent_resource['collection_name']
            p_member = parent_resource['member_name']
            kwargs['path_prefix'] = '%s/:%s_id' % (p_collection, p_member)
        routes.Mapper.resource(self, member_name,
                                     collection_name,
                                     **kwargs)


class APIRouter(base_wsgi.Router):
    """
    Routes requests on the OpenStack API to the appropriate controller
    and method.
    根据请求信息实现路由OpenStack API到匹配的控制器和方法上；
    """
    
    ExtensionManager = None  # override in subclasses

    @classmethod
    def factory(cls, global_config, **local_config):
        """
        Simple paste factory, :class:`nova.wsgi.Router` doesn't have one.
        """
        return cls()

    def __init__(self, ext_mgr=None, init_only=None):
        """
        ======================================================================================
        ext_mgr = None
        self.ExtensionManager = <class 'nova.api.openstack.compute.extensions.ExtensionManager'>
        ======================================================================================
        """
        """
        self.ExtensionManager()：
        遍历contrib,实现了所有的API扩展功能的注册；
        """
        if ext_mgr is None:
            if self.ExtensionManager:
                ext_mgr = self.ExtensionManager()
            else:
                raise Exception(_("Must specify an ExtensionManager class"))

        mapper = ProjectMapper()
        self.resources = {}
        """
        正规API方法的加载以及其路由表的生成；
        """
        self._setup_routes(mapper, ext_mgr, init_only)
        """
        针对get_resources方法中的controller类中的扩展方法实现生成路由表；
        """
        self._setup_ext_routes(mapper, ext_mgr, init_only)
        """
        获取所有扩展文件中具体实现了get_controller_extensions方法的集合；
        1 获取controller指定的wsgi_action装饰器装饰的扩展方法；
          存储在self.wsgi_actions中；
        2 获取所有wsgi.extends装饰的扩展方法，有action参数的；
          存储在self.wsgi_action_extensions中；
          @wsgi.extends(action='create')
        3 获取所有wsgi.extends装饰的扩展方法，没有action参数的；
          存储在self.wsgi_extensions中；
          @wsgi.extends
        """
        self._setup_extensions(ext_mgr)
        super(APIRouter, self).__init__(mapper)


    def _setup_ext_routes(self, mapper, ext_mgr, init_only):
        """
        针对get_resources方法中的controller类中的扩展方法实现生成路由表；
        """
        """
        API扩展文件中，实现get_resources方法；
        """
        for resource in ext_mgr.get_resources():
            LOG.debug(_('Extending resource: %s'),
                      resource.collection)

            if init_only is not None and resource.collection not in init_only:
                continue

            inherits = None
            
            if resource.inherits:
                inherits = self.resources.get(resource.inherits)
                if not resource.controller:
                    resource.controller = inherits.controller
            
            """
            针对get_resources方法中的controller类：
            """
            wsgi_resource = wsgi.Resource(resource.controller,
                                          inherits=inherits)
            self.resources[resource.collection] = wsgi_resource
            kargs = dict(
                controller=wsgi_resource,
                collection=resource.collection_actions,
                member=resource.member_actions)

            if resource.parent:
                kargs['parent_resource'] = resource.parent

            """
            针对get_resources方法中的controller类中的扩展方法实现生成路由表；
            """
            mapper.resource(resource.collection, resource.collection, **kargs)

            if resource.custom_routes_fn:
                resource.custom_routes_fn(mapper, wsgi_resource)

    def _setup_extensions(self, ext_mgr):
        """
        get_controller_extensions:
        获取所有扩展文件中具体实现了get_controller_extensions方法的集合；
        1 获取controller指定的wsgi_action装饰器装饰的扩展方法；
          存储在self.wsgi_actions中；
        2 获取所有wsgi.extends装饰的扩展方法，有action参数的；
          存储在self.wsgi_action_extensions中；
          @wsgi.extends(action='create')
        3 获取所有wsgi.extends装饰的扩展方法，没有action参数的；
          存储在self.wsgi_action_extensions中；
          @wsgi.extends
        """
        for extension in ext_mgr.get_controller_extensions():
            collection = extension.collection
            controller = extension.controller

            msg_format_dict = {'collection': collection,
                               'ext_name': extension.extension.name}
            if collection not in self.resources:
                LOG.warning(_('Extension %(ext_name)s: Cannot extend '
                              'resource %(collection)s: No such resource'),
                            msg_format_dict)
                continue

            LOG.debug(_('Extension %(ext_name)s extended resource: '
                        '%(collection)s'),
                      msg_format_dict)

            resource = self.resources[collection]
            
            """
            获取controller指定的wsgi_action装饰器装饰的扩展方法；
            存储在self.wsgi_actions中；
            """
            resource.register_actions(controller)
            """
            获取所有wsgi.extends装饰的扩展方法，有action参数的；
            存储在self.wsgi_action_extensions中；
            @wsgi.extends(action='create')
            获取所有wsgi.extends装饰的扩展方法，没有action参数的；
            存储在self.wsgi_action_extensions中；
            @wsgi.extends
            """
            resource.register_extensions(controller)

    def _setup_routes(self, mapper, ext_mgr, init_only):
        raise NotImplementedError()