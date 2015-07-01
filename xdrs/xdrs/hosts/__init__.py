"""
主机有关的若干操作；
"""

import xdrs.openstack.common.importutils

"""
注：这里可以进行扩展；
"""
CLS_NAME = {'host_api': 'xdrs.hosts.api.API',
            'host_to_global_api': 'xdrs.hosts.api.HostToGlobalAPI'}


def _get_api_class_name(compute_type):
    return CLS_NAME[compute_type]


def API(*args, **kwargs):
    importutils = xdrs.openstack.common.importutils
    class_name = _get_api_class_name(compute_type = 'host_api')
    return importutils.import_object(class_name, *args, **kwargs)

def HostToGlobalAPI(*args, **kwargs):
    importutils = xdrs.openstack.common.importutils
    class_name = _get_api_class_name(compute_type = 'host_api')
    return importutils.import_object(class_name, *args, **kwargs)