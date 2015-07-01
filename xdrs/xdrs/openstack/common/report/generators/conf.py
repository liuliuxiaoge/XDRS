"""
Provides Openstack config generators
"""

from oslo.config import cfg

import xdrs.openstack.common.report.models.conf as cm


class ConfigReportGenerator(object):
    """
    A Configuration Data Generator
    """

    def __init__(self, cnf=cfg.CONF):
        self.conf_obj = cnf

    def __call__(self):
        return cm.ConfigModel(self.conf_obj)
