"""
SQLAlchemy models.
"""

import six

from sqlalchemy import Column, Integer
from sqlalchemy import DateTime
from sqlalchemy.orm import object_mapper

from xdrs.openstack.common import timeutils


class ModelBase(object):
    """Base class for models."""
    __table_initialized__ = False

    def save(self, session):
        """Save this object."""
        with session.begin(subtransactions=True):
            session.add(self)
            session.flush()

    def __setitem__(self, key, value):
        setattr(self, key, value)

    def __getitem__(self, key):
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key, default)

    @property
    def _extra_keys(self):
        """
        Specifies custom fields
        """
        return []

    def __iter__(self):
        columns = dict(object_mapper(self).columns).keys()
        # NOTE(russellb): Allow models to specify other keys that can be looked
        # up, beyond the actual db columns.  An example would be the 'name'
        # property for an Instance.
        columns.extend(self._extra_keys)
        self._i = iter(columns)
        return self

    def next(self):
        n = six.advance_iterator(self._i)
        return n, getattr(self, n)

    def update(self, values):
        """Make the model object behave like a dict."""
        for k, v in six.iteritems(values):
            setattr(self, k, v)

    def iteritems(self):
        """
        Make the model object behave like a dict.
        """
        local = dict(self)
        joined = dict([(k, v) for k, v in six.iteritems(self.__dict__)
                      if not k[0] == '_'])
        local.update(joined)
        return six.iteritems(local)


class TimestampMixin(object):
    created_at = Column(DateTime, default=lambda: timeutils.utcnow())
    updated_at = Column(DateTime, onupdate=lambda: timeutils.utcnow())


class SoftDeleteMixin(object):
    deleted_at = Column(DateTime)
    deleted = Column(Integer, default=0)

    def soft_delete(self, session):
        """Mark this object as deleted."""
        self.deleted = self.id
        self.deleted_at = timeutils.utcnow()
        self.save(session=session)
