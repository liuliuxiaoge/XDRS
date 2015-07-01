"""
Provides Openstack Version Info Model
"""

import xdrs.openstack.common.report.models.with_default_views as mwdv
import xdrs.openstack.common.report.views.text.generic as generic_text_views


class PackageModel(mwdv.ModelWithDefaultViews):
    """
    A Package Information Model

    This model holds information about the current
    package.  It contains vendor, product, and version
    information.

    :param str vendor: the product vendor
    :param str product: the product name
    :param str version: the product version
    """

    def __init__(self, vendor, product, version):
        super(PackageModel, self).__init__(
            text_view=generic_text_views.KeyValueView()
        )

        self['vendor'] = vendor
        self['product'] = product
        self['version'] = version
