"""
Provides generic JSON views
"""

import copy

from xdrs.openstack.common import jsonutils as json
import xdrs.openstack.common.report.utils as utils


class BasicKeyValueView(object):
    """
    A Basic Key-Value JSON View
    """

    def __call__(self, model):
        res = utils.StringWithAttrs(json.dumps(model.data))
        res.__is_json__ = True
        return res


class KeyValueView(object):
    """
    A Key-Value JSON View
    """

    def __call__(self, model):
        # this part deals with subviews that were already serialized
        cpy = copy.deepcopy(model)
        for key, valstr in model.items():
            if getattr(valstr, '__is_json__', False):
                cpy[key] = json.loads(valstr)

        res = utils.StringWithAttrs(json.dumps(cpy.data))
        res.__is_json__ = True
        return res
