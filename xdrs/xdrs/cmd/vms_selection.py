import sys

from oslo.config import cfg

from xdrs import config
from xdrs.openstack.common import log as logging
from xdrs.openstack.common.report import guru_meditation_report as gmr
from xdrs import service
from xdrs import utils
from xdrs import version

CONF = cfg.CONF
CONF.import_opt('vms_selection_topic', 'xdrs.service')

def main():
    config.parse_args(sys.argv)
    logging.setup("xdrs")
    utils.monkey_patch()

    gmr.TextGuruMeditation.setup_autorun(version)

    server = service.Service.create(binary='xdrs_vms_selection',
                                    topic=CONF.vms_selection_topic)
    service.serve(server)
    service.wait()