"""
Simple class that stores security context information in the web request.
"""

import itertools
from xdrs.openstack.common import uuidutils


def generate_request_id():
    return 'req-%s' % uuidutils.generate_uuid()


class RequestContext(object):
    """
    Helper class to represent useful information about a request context.
    """

    def __init__(self, auth_token=None, user=None, tenant=None, is_admin=False,
                 read_only=False, show_deleted=False, request_id=None):
        self.auth_token = auth_token
        self.user = user
        self.tenant = tenant
        self.is_admin = is_admin
        self.read_only = read_only
        self.show_deleted = show_deleted
        if not request_id:
            request_id = generate_request_id()
        self.request_id = request_id

    def to_dict(self):
        return {'user': self.user,
                'tenant': self.tenant,
                'is_admin': self.is_admin,
                'read_only': self.read_only,
                'show_deleted': self.show_deleted,
                'auth_token': self.auth_token,
                'request_id': self.request_id}


def get_admin_context(show_deleted=False):
    context = RequestContext(None,
                             tenant=None,
                             is_admin=True,
                             show_deleted=show_deleted)
    return context


def get_context_from_function_and_args(function, args, kwargs):
    """
    Find an arg of type RequestContext and return it.
    """

    for arg in itertools.chain(kwargs.values(), args):
        if isinstance(arg, RequestContext):
            return arg

    return None
