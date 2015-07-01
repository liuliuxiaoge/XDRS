"""
Starter script for Xdrs Scheduler.
"""

import sys

from oslo.config import cfg

from xdrs import config
from xdrs.openstack.common import log as logging
from xdrs.openstack.common.report import guru_meditation_report as gmr
from xdrs import service
from xdrs import utils
from xdrs import version

CONF = cfg.CONF
CONF.import_opt('conductor_topic', 'xdrs.service')


def main():
    config.parse_args(sys.argv)
    """
    这里需要进行另外的分析；
    """
    logging.setup("xdrs")
    utils.monkey_patch()
    
    gmr.TextGuruMeditation.setup_autorun(version)

    server = service.Service.create(binary='xdrs_conductor',
                                    topic=CONF.conductor_topic)
    service.serve(server)
    service.wait()