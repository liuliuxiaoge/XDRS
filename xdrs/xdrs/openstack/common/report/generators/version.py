"""
Provides Openstack version generators
"""

import xdrs.openstack.common.report.models.version as vm


class PackageReportGenerator(object):
    def __init__(self, version_obj):
        self.version_obj = version_obj

    def __call__(self):
        return vm.PackageModel(
            self.version_obj.vendor_string(),
            self.version_obj.product_string(),
            self.version_obj.version_string_with_package())
