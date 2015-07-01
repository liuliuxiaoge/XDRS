"""
安全的上下文环境信息的处理；
"""

import copy
import uuid

import six

from xdrs import exception
from xdrs.openstack.common.gettextutils import _
from xdrs.openstack.common import local
from xdrs.openstack.common import log as logging
from xdrs.openstack.common import timeutils
from xdrs import policy


LOG = logging.getLogger(__name__)


def generate_request_id():
    return 'req-' + str(uuid.uuid4())


class RequestContext(object):
    """
    Represents the user taking a given action within the system.
    安全的上下文环境信息和请求信息；
    """
    def __init__(self, user_id, project_id, is_admin=None, read_deleted="no",
                 roles=None, remote_address=None, timestamp=None,
                 request_id=None, auth_token=None, overwrite=True,
                 quota_class=None, user_name=None, project_name=None,
                 service_catalog=None, instance_lock_checked=False, **kwargs):
        if kwargs:
            LOG.warn(_('Arguments dropped when creating context: %s') %
                    str(kwargs))

        self.user_id = user_id
        self.project_id = project_id
        self.roles = roles or []
        self.read_deleted = read_deleted
        self.remote_address = remote_address
        if not timestamp:
            timestamp = timeutils.utcnow()
        if isinstance(timestamp, six.string_types):
            timestamp = timeutils.parse_strtime(timestamp)
        self.timestamp = timestamp
        if not request_id:
            request_id = generate_request_id()
        self.request_id = request_id
        self.auth_token = auth_token

        if service_catalog:
            # Only include required parts of service_catalog
            self.service_catalog = [s for s in service_catalog
                if s.get('type') in ('volume',)]
        else:
            # if list is empty or none
            self.service_catalog = []

        self.instance_lock_checked = instance_lock_checked
        self.quota_class = quota_class
        self.user_name = user_name
        self.project_name = project_name
        self.is_admin = is_admin
        if self.is_admin is None:
            self.is_admin = policy.check_is_admin(self)
        if overwrite or not hasattr(local.store, 'context'):
            self.update_store()

    def _get_read_deleted(self):
        return self._read_deleted

    def _set_read_deleted(self, read_deleted):
        if read_deleted not in ('no', 'yes', 'only'):
            raise ValueError(_("read_deleted can only be one of 'no', "
                               "'yes' or 'only', not %r") % read_deleted)
        self._read_deleted = read_deleted

    def _del_read_deleted(self):
        del self._read_deleted

    read_deleted = property(_get_read_deleted, _set_read_deleted,
                            _del_read_deleted)

    def update_store(self):
        local.store.context = self

    def to_dict(self):
        return {'user_id': self.user_id,
                'project_id': self.project_id,
                'is_admin': self.is_admin,
                'read_deleted': self.read_deleted,
                'roles': self.roles,
                'remote_address': self.remote_address,
                'timestamp': timeutils.strtime(self.timestamp),
                'request_id': self.request_id,
                'auth_token': self.auth_token,
                'quota_class': self.quota_class,
                'user_name': self.user_name,
                'service_catalog': self.service_catalog,
                'project_name': self.project_name,
                'instance_lock_checked': self.instance_lock_checked,
                'tenant': self.tenant,
                'user': self.user}

    @classmethod
    def from_dict(cls, values):
        values.pop('user', None)
        values.pop('tenant', None)
        return cls(**values)

    def elevated(self, read_deleted=None, overwrite=False):
        """Return a version of this context with admin flag set."""
        context = copy.copy(self)
        context.is_admin = True

        if 'admin' not in context.roles:
            context.roles.append('admin')

        if read_deleted is not None:
            context.read_deleted = read_deleted

        return context
    
    
    @property
    def tenant(self):
        return self.project_id

    @property
    def user(self):
        return self.user_id


def get_admin_context(read_deleted="no"):
    """
    获取admin的上下文环境；
    """
    return RequestContext(user_id=None,
                          project_id=None,
                          is_admin=True,
                          read_deleted=read_deleted,
                          overwrite=False)


def is_user_context(context):
    """
    Indicates if the request context is a normal user.
    要求普通user的上下文环境；
    """
    if not context:
        return False
    if context.is_admin:
        return False
    if not context.user_id or not context.project_id:
        return False
    return True


def require_admin_context(ctxt):
    """
    Raise exception.AdminRequired() if context is an admin context.
    要求admin的上下文环境；
    """
    if not ctxt.is_admin:
        raise exception.AdminRequired()


def require_context(ctxt):
    """
    Raise exception.NotAuthorized() if context is not a user or an
    admin context.
    """
    if not ctxt.is_admin and not is_user_context(ctxt):
        raise exception.NotAuthorized()


def authorize_project_context(context, project_id):
    """
    Ensures a request has permission to access the given project.
    确认有权限访问给定的project；
    """
    if is_user_context(context):
        if not context.project_id:
            raise exception.NotAuthorized()
        elif context.project_id != project_id:
            raise exception.NotAuthorized()


def authorize_user_context(context, user_id):
    """
    Ensures a request has permission to access the given user.
    确认有权限访问给定的user；
    """
    if is_user_context(context):
        if not context.user_id:
            raise exception.NotAuthorized()
        elif context.user_id != user_id:
            raise exception.NotAuthorized()


def authorize_quota_class_context(context, class_name):
    """
    Ensures a request has permission to access the given quota class.
    确认有权限访问给定的class_name；
    """
    if is_user_context(context):
        if not context.quota_class:
            raise exception.NotAuthorized()
        elif context.quota_class != class_name:
            raise exception.NotAuthorized()