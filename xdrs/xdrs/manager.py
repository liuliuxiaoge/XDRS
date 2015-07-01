"""
manager基类；
"""

from oslo.config import cfg

from xdrs.db import base
from xdrs.openstack.common import log as logging
from xdrs.openstack.common import periodic_task
from xdrs import rpc


CONF = cfg.CONF
LOG = logging.getLogger(__name__)


class Manager(base.Base, periodic_task.PeriodicTasks):

    def __init__(self, host=None, db_driver=None, service_name='undefined'):
        if not host:
            host = CONF.host
        self.host = host
        self.backdoor_port = None
        self.service_name = service_name
        self.notifier = rpc.get_notifier(self.service_name, self.host)
        self.additional_endpoints = []
        super(Manager, self).__init__(db_driver)

    """
    非常重要；
    """
    def periodic_tasks(self, context, raise_on_error=False):
        """
        Tasks to be run at a periodic interval.
        """
        return self.run_periodic_tasks(context, raise_on_error=raise_on_error)

    def init_host(self):
        """
        Hook to do additional manager initialization when one requests
        the service be started.  This is called before any service record
        is created.
        """
        pass

    def cleanup_host(self):
        """
        Hook to do cleanup work when the service shuts down.
        """
        pass

    def pre_start_hook(self):
        """
        Hook to provide the manager the ability to do additional
        start-up work before any RPC queues/consumers are created. This is
        called after other initialization has succeeded and a service
        record is created.
        Child classes should override this method.
        """
        pass

    def post_start_hook(self):
        """
        Hook to provide the manager the ability to do additional
        start-up work immediately after a service creates RPC consumers
        and starts 'running'.
        Child classes should override this method.
        """
        pass
