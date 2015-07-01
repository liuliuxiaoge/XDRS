"""
DB related custom exceptions.
"""

import six

from xdrs.openstack.common.gettextutils import _


class DBError(Exception):
    """Wraps an implementation specific exception."""
    def __init__(self, inner_exception=None):
        self.inner_exception = inner_exception
        super(DBError, self).__init__(six.text_type(inner_exception))


class DBDuplicateEntry(DBError):
    """Wraps an implementation specific exception."""
    def __init__(self, columns=[], inner_exception=None):
        self.columns = columns
        super(DBDuplicateEntry, self).__init__(inner_exception)


class DBDeadlock(DBError):
    def __init__(self, inner_exception=None):
        super(DBDeadlock, self).__init__(inner_exception)


class DBInvalidUnicodeParameter(Exception):
    message = _("Invalid Parameter: "
                "Unicode is not supported by the current database.")


class DbMigrationError(DBError):
    """Wraps migration specific exception."""
    def __init__(self, message=None):
        super(DbMigrationError, self).__init__(message)


class DBConnectionError(DBError):
    """Wraps connection specific exception."""
    pass
