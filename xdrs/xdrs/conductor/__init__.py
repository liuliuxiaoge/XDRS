"""
conductor的功能实现API入口；
"""

import oslo.config.cfg
from xdrs.conductor import api as conductor_api


def API(*args, **kwargs):
    use_local = kwargs.pop('use_local', False)
    if oslo.config.cfg.CONF.conductor.use_local or use_local:
        api = conductor_api.LocalAPI
    else:
        api = conductor_api.API
    return api(*args, **kwargs)


def ComputeTaskAPI(*args, **kwargs):
    use_local = kwargs.pop('use_local', False)
    if oslo.config.cfg.CONF.conductor.use_local or use_local:
        api = conductor_api.LocalComputeTaskAPI
    else:
        api = conductor_api.ComputeTaskAPI
    return api(*args, **kwargs)