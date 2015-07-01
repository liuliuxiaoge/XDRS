"""
Base class for classes that need modular database access.
"""

from oslo.config import cfg
from xdrs.openstack.common import importutils


db_driver_opt = cfg.StrOpt('db_driver',
                           default='nova.db',
                           help='The driver to use for database access')

CONF = cfg.CONF
CONF.register_opt(db_driver_opt)


class Base(object):
    """DB driver is injected in the init method."""

    def __init__(self, db_driver=None):
        super(Base, self).__init__()
        if not db_driver:
            db_driver = CONF.db_driver
        self.db = importutils.import_module(db_driver)  # pylint: disable=C0103
