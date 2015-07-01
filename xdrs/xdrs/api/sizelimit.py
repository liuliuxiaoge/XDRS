"""
Request Body limiting middleware.
limit中间件的实现，用于检测请求信息body部分的长度是否合法；
"""

from oslo.config import cfg
import webob.dec
import webob.exc

from xdrs.openstack.common.gettextutils import _
from xdrs import wsgi


max_request_body_size_opt = cfg.IntOpt('osapi_max_request_body_size',
                                       default=114688,
                                       help='The maximum body size '
                                            'per each osapi request(bytes)')

CONF = cfg.CONF
CONF.register_opt(max_request_body_size_opt)


class LimitingReader(object):
    """
    Reader to limit the size of an incoming request.
    """
    def __init__(self, data, limit):
        """
        Initialize a new `LimitingReader`.
        """
        self.data = data
        self.limit = limit
        self.bytes_read = 0

    def __iter__(self):
        for chunk in self.data:
            self.bytes_read += len(chunk)
            if self.bytes_read > self.limit:
                msg = _("Request is too large.")
                raise webob.exc.HTTPRequestEntityTooLarge(explanation=msg)
            else:
                yield chunk

    def read(self, i=None):
        result = self.data.read(i)
        self.bytes_read += len(result)
        if self.bytes_read > self.limit:
            msg = _("Request is too large.")
            raise webob.exc.HTTPRequestEntityTooLarge(explanation=msg)
        return result

class RequestBodySizeLimiter(wsgi.Middleware):
    """
    Limit the size of incoming requests.
    """

    def __init__(self, *args, **kwargs):
        super(RequestBodySizeLimiter, self).__init__(*args, **kwargs)

    @webob.dec.wsgify(RequestClass=wsgi.Request)
    def __call__(self, req):
        if req.content_length > CONF.osapi_max_request_body_size:
            msg = _("Request is too large.")
            raise webob.exc.HTTPRequestEntityTooLarge(explanation=msg)
        if req.content_length is None and req.is_body_readable:
            limiter = LimitingReader(req.body_file,
                                     CONF.osapi_max_request_body_size)
            req.body_file = limiter
        return self.application
