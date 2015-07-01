"""
控制节点上的若干操作；
"""

import xdrs.openstack.common.importutils

"""
注：这里可以进行扩展；
"""
CLS_NAME = {'controller_api': 'xdrs.controller.api.API'}


def _get_api_class_name():
    compute_type = 'controller_api'
    return CLS_NAME[compute_type]


def API(*args, **kwargs):
    importutils = xdrs.openstack.common.importutils
    class_name = _get_api_class_name()
    return importutils.import_object(class_name, *args, **kwargs)