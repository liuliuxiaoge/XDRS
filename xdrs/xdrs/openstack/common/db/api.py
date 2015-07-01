"""
Multiple DB API backend support.
"""

import functools
import logging
import threading
import time

from xdrs.openstack.common.db import exception
from xdrs.openstack.common.gettextutils import _LE
from xdrs.openstack.common import importutils


LOG = logging.getLogger(__name__)


def safe_for_db_retry(f):
    """
    Enable db-retry for decorated function, if config option enabled.
    """
    f.__dict__['enable_retry'] = True
    return f


class wrap_db_retry(object):
    """
    Retry db.api methods, if DBConnectionError() raised
    """

    def __init__(self, retry_interval, max_retries, inc_retry_interval,
                 max_retry_interval):
        super(wrap_db_retry, self).__init__()

        self.retry_interval = retry_interval
        self.max_retries = max_retries
        self.inc_retry_interval = inc_retry_interval
        self.max_retry_interval = max_retry_interval

    def __call__(self, f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            next_interval = self.retry_interval
            remaining = self.max_retries

            while True:
                try:
                    return f(*args, **kwargs)
                except exception.DBConnectionError as e:
                    if remaining == 0:
                        LOG.exception(_LE('DB exceeded retry limit.'))
                        raise exception.DBError(e)
                    if remaining != -1:
                        remaining -= 1
                        LOG.exception(_LE('DB connection error.'))
                    # NOTE(vsergeyev): We are using patched time module, so
                    #                  this effectively yields the execution
                    #                  context to another green thread.
                    time.sleep(next_interval)
                    if self.inc_retry_interval:
                        next_interval = min(
                            next_interval * 2,
                            self.max_retry_interval
                        )
        return wrapper


class DBAPI(object):
    def __init__(self, backend_name, backend_mapping=None, lazy=False,
                 **kwargs):
        """
        Initialize the chosen DB API backend.
        """

        self._backend = None
        self._backend_name = backend_name
        self._backend_mapping = backend_mapping or {}
        self._lock = threading.Lock()

        if not lazy:
            self._load_backend()

        self.use_db_reconnect = kwargs.get('use_db_reconnect', False)
        self.retry_interval = kwargs.get('retry_interval', 1)
        self.inc_retry_interval = kwargs.get('inc_retry_interval', True)
        self.max_retry_interval = kwargs.get('max_retry_interval', 10)
        self.max_retries = kwargs.get('max_retries', 20)

    def _load_backend(self):
        with self._lock:
            if not self._backend:
                # Import the untranslated name if we don't have a mapping
                backend_path = self._backend_mapping.get(self._backend_name,
                                                         self._backend_name)
                backend_mod = importutils.import_module(backend_path)
                self._backend = backend_mod.get_backend()

    def __getattr__(self, key):
        if not self._backend:
            self._load_backend()

        attr = getattr(self._backend, key)
        if not hasattr(attr, '__call__'):
            return attr
        # NOTE(vsergeyev): If `use_db_reconnect` option is set to True, retry
        #                  DB API methods, decorated with @safe_for_db_retry
        #                  on disconnect.
        if self.use_db_reconnect and hasattr(attr, 'enable_retry'):
            attr = wrap_db_retry(
                retry_interval=self.retry_interval,
                max_retries=self.max_retries,
                inc_retry_interval=self.inc_retry_interval,
                max_retry_interval=self.max_retry_interval)(attr)

        return attr
