"""
主机有关的若干操作；
"""

import xdrs.openstack.common.importutils

"""
注：这里可以进行扩展；
"""
CLS_NAME = {'vm_api': 'xdrs.vms.api.API'}


def _get_api_class_name():
    compute_type = 'vm_api'
    return CLS_NAME[compute_type]


def API(*args, **kwargs):
    importutils = xdrs.openstack.common.importutils
    class_name = _get_api_class_name()
    return importutils.import_object(class_name, *args, **kwargs)