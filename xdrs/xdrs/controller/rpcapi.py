from oslo.config import cfg
from oslo import messaging

from xdrs.objects import base as objects_base
from xdrs import rpc
from xdrs.openstack.common import jsonutils

CONF = cfg.CONF
CONF.import_opt('controller_topic', 'xdrs.service')
CONF.import_opt('data_collection_topic', 'xdrs.service')
CONF.import_opt('load_detection_topic', 'xdrs.service')
CONF.import_opt('vms_migration_topic', 'xdrs.service')
CONF.import_opt('vms_selection_topic', 'xdrs.service')

class ControllerRPCAPI(object):
    def __init__(self):
        super(ControllerRPCAPI, self).__init__()
        target = messaging.Target(topic=CONF.controller_topic)
        """
        objects_base.XdrsObjectSerializer需要进行进一步实现，还未完成；
        """
        serializer = objects_base.XdrsObjectSerializer()
        self.client = self.get_client(target, serializer)

    def get_client(self, target, serializer):
        return rpc.get_client(target,
                              serializer=serializer)
        
    
    """
    **************
    * host_power *
    **************
    """
    def switch_host_off(self, context, sleep_command, host, controller_topic):
        if controller_topic != CONF.controller_topic:
            return False
        cctxt = self.client.prepare(server = host)
        sleep_command = jsonutils.to_primitive(sleep_command)
        controller_topic = jsonutils.to_primitive(controller_topic)
        cctxt.cast(context, 'switch_host_off', sleep_command=sleep_command, controller_topic=controller_topic)
        
    def switch_host_on(self, context, ether_wake_interface, host_macs, host):
        cctxt = self.client.prepare(server = host)
        cctxt.cast(context, 'switch_host_on', 
                       ether_wake_interface=ether_wake_interface,
                       host_macs=host_macs)
        

class DataCollectionRPCAPI(object):
    def __init__(self):
        super(DataCollectionRPCAPI, self).__init__()
        target = messaging.Target(topic=CONF.data_collection_topic)
        """
        objects_base.XdrsObjectSerializer需要进行进一步实现，还未完成；
        """
        serializer = objects_base.XdrsObjectSerializer()
        self.client = self.get_client(target, serializer)

    # Cells overrides this
    def get_client(self, target, serializer):
        return rpc.get_client(target,
                              serializer=serializer)
    
    def hosts_vms_data_collection(self, context, data_collection_topic):
        if data_collection_topic != CONF.data_collection_topic:
            return False
        data_collection_topic = jsonutils.to_primitive(data_collection_topic)
        cctxt = self.client.prepare()
        return cctxt.call(context, 'hosts_vms_data_collection')
    

class LoadDetectionRPCAPI(object):
    def __init__(self):
        super(LoadDetectionRPCAPI, self).__init__()
        target = messaging.Target(topic=CONF.load_detection_topic)
        """
        objects_base.XdrsObjectSerializer需要进行进一步实现，还未完成；
        """
        serializer = objects_base.XdrsObjectSerializer()
        self.client = self.get_client(target, serializer)

    # Cells overrides this
    def get_client(self, target, serializer):
        return rpc.get_client(target,
                              serializer=serializer) 
    
    def hosts_load_detection(self, context, load_detection_topic):
        if load_detection_topic != CONF.load_detection_topic:
            return False
        cctxt = self.client.prepare()
        return cctxt.call(context, 'hosts_load_detection')
    

class VmsSelectionRPCAPI(object):
    def __init__(self):
        super(VmsSelectionRPCAPI, self).__init__()
        target = messaging.Target(topic=CONF.vms_selection_topic)
        """
        objects_base.XdrsObjectSerializer需要进行进一步实现，还未完成；
        """
        serializer = objects_base.XdrsObjectSerializer()
        self.client = self.get_client(target, serializer)

    # Cells overrides this
    def get_client(self, target, serializer):
        return rpc.get_client(target,
                              serializer=serializer) 
    
    def vms_selection(self, context, host_uuid, vms_selection_topic):
        if vms_selection_topic != CONF.vms_selection_topic:
            return False
        load_detection_topic = jsonutils.to_primitive(vms_selection_topic)
        cctxt = self.client.prepare(server = host_uuid)
        return cctxt.call(context, 'vms_selection', vms_selection_topic=vms_selection_topic)


class VmMigrationRPCAPI(object):
    def __init__(self):
        super(VmMigrationRPCAPI, self).__init__()
        target = messaging.Target(topic=CONF.vms_migration_topic)
        """
        objects_base.XdrsObjectSerializer需要进行进一步实现，还未完成；
        """
        serializer = objects_base.XdrsObjectSerializer()
        self.client = self.get_client(target, serializer)

    # Cells overrides this
    def get_client(self, target, serializer):
        return rpc.get_client(target,
                              serializer=serializer) 
    
    def vms_migration(self, context, vms_migration_topic):
        if vms_migration_topic != CONF.vms_migration_topic:
            return False
        vms_migration_topic = jsonutils.to_primitive(vms_migration_topic)
        cctxt = self.client.prepare()
        return cctxt.call(context, 'vms_migration', vms_migration_topic=vms_migration_topic)