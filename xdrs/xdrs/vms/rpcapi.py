from oslo.config import cfg
from oslo import messaging

from xdrs.objects import base as objects_base
from xdrs import rpc


vms_opts = [
            cfg.StrOpt('vm_topic',
               default='xdrs_vm')
           ]

CONF = cfg.CONF
CONF.register_opts(vms_opts)


class VmRPCAPI(object):
    def __init__(self):
        super(VmRPCAPI, self).__init__()
        target = messaging.Target(topic=CONF.vm_topic)
        """
        objects_base.XdrsObjectSerializer需要进行进一步实现，还未完成；
        """
        serializer = objects_base.XdrsObjectSerializer()
        self.client = self.get_client(target, serializer)

    # Cells overrides this
    def get_client(self, target, serializer):
        return rpc.get_client(target,
                              serializer=serializer)