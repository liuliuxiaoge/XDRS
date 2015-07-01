"""
SQLAlchemy models for xdrs data.
"""

from sqlalchemy import Column, Integer, String, schema
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import DateTime, Boolean, UnicodeText
from oslo.config import cfg

from xdrs.openstack.common.db.sqlalchemy import models

BASE = declarative_base()

class XdrsBase(models.SoftDeleteMixin,
               models.TimestampMixin,
               models.ModelBase):
    metadata = None

    def save(self, session=None):
        from xdrs.db.sqlalchemy import api

        if session is None:
            session = api.get_session()

        super(XdrsBase, self).save(session=session)
        
        
class Service(BASE, XdrsBase):
    """
    Represents a running service on a host.
    表示在主机上正在运行的服务；
    """

    __tablename__ = 'services'
    __table_args__ = (
        schema.UniqueConstraint("host", "topic", "deleted",
                                name="uniq_services0host0topic0deleted"),
        schema.UniqueConstraint("host", "binary", "deleted",
                                name="uniq_services0host0binary0deleted")
        )

    id = Column(Integer, primary_key=True)
    host_name = Column(String(255))  # , ForeignKey('hosts.id'))
    binary = Column(String(255))
    topic = Column(String(255))
    disabled = Column(Boolean, default=False)
    disabled_reason = Column(String(255))
    
    
class VmMetadata(BASE, XdrsBase):
    
    __tablename__ = 'vm_metadata'
    __table_args__ = ()
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String(255))
    project_id = Column(String(255))
    vm_state = Column(String(255))
    host_name = Column(String(255))
    host_id = Column(String(255))
    

class VmMigrationRecord(BASE, XdrsBase):
    
    __tablename__ = 'vm_migration_record'
    __table_args__ = ()
    
    id = Column(Integer, primary_key=True)
    vm_id = Column(String(255))
    current_host_name = Column(String(255))
    current_host_id = Column(String(255))
    previous_host_name = Column(String(255))
    previous_host_id = Column(String(255))
    timestamp = Column(DateTime)
    task_state = Column(String(255))
    
      
class HostTaskState(BASE, XdrsBase):
    __tablename__ = 'host_task_state'
    __table_args__ = ()
    
    id = Column(Integer, primary_key=True)
    host_name = Column(String(255))
    host_task_state = Column(String(255))
    #有待商榷；
    migration_time = Column(DateTime)
    detection_time = Column(DateTime)
    
    
class HostRunningState(BASE, XdrsBase):
    __tablename__ = 'host_running_state'
    __table_args__ = ()
    
    id = Column(Integer, primary_key=True)
    host_name = Column(String(255))
    host_running_state = Column(String(255))
    
    
class HostLoadState(BASE, XdrsBase):
    __tablename__ = 'host_load_state'
    __table_args__ = ()
    
    id = Column(Integer, primary_key=True)
    host_name = Column(String(255))
    host_load_state = Column(String(255))
    

class VmCpuData(BASE, XdrsBase):
    __tablename__ = 'vm_cpu_data'
    __table_args__ = ()
    
    vm_id = Column(Integer, primary_key=True)
    host_id = Column(String(255))
    host_name = Column(String(255))
    data_len = Column(Integer)
    cpu_data = Column(UnicodeText)
    delete_reason = Column(UnicodeText)
    

class HostCpuData(BASE, XdrsBase):
    __tablename__ = 'host_cpu_data'
    __table_args__ = ()
    
    host_name = Column(String(255))
    host_id = Column(String(255))
    data_len = Column(Integer)
    cpu_data = Column(UnicodeText)
    delete_reason = Column(UnicodeText)


class HostCpuDataTemp(BASE, XdrsBase):
    __tablename__ = 'host_cpu_data_temp'
    __table_args__ = ()
    
    host_id = Column(String(255))
    cpu_data = Column(UnicodeText)
    hosts_total_ram = Column(String(255))
    hosts_free_ram = Column(String(255))


class UnderloadAlgorithms(BASE, XdrsBase):
    __tablename__ = 'underload_algorithms'
    __table_args__ = ()
    
    algorithm_name = Column(String(255))
    id = Column(Integer)
    algorithm_id = Column(String(255))
    algorithm_params = Column(String(255))
    description = Column(UnicodeText)
    in_used = Column(Boolean, default=False)
    

class OverloadAlgorithms(BASE, XdrsBase):
    __tablename__ = 'overload_algorithms'
    __table_args__ = ()
    
    algorithm_name = Column(String(255))
    id = Column(Integer)
    algorithm_id = Column(String(255))
    algorithm_params = Column(String(255))
    description = Column(UnicodeText)
    in_used = Column(Boolean, default=False)
    
    
class FilterSchedulerAlgorithms(BASE, XdrsBase):
    __tablename__ = 'filter_scheduler_algorithms'
    __table_args__ = ()
    
    algorithm_name = Column(String(255))
    id = Column(Integer)
    algorithm_id = Column(String(255))
    algorithm_params = Column(String(255))
    description = Column(UnicodeText)
    in_used = Column(Boolean, default=False)
    
    
class HostSchedulerAlgorithms(BASE, XdrsBase):
    __tablename__ = 'host_scheduler_algorithms'
    __table_args__ = ()
    
    algorithm_name = Column(String(255))
    id = Column(Integer)
    algorithm_id = Column(String(255))
    algorithm_params = Column(String(255))
    description = Column(UnicodeText)
    in_used = Column(Boolean, default=False)
    
    
class VmSelectAlgorithms(BASE, XdrsBase):
    __tablename__ = 'vm_select_algorithms'
    __table_args__ = ()
    
    algorithm_name = Column(String(255))
    id = Column(Integer)
    algorithm_id = Column(String(255))
    algorithm_params = Column(String(255))
    description = Column(UnicodeText)
    in_used = Column(Boolean, default=False)
    
    
class HostInitData(BASE, XdrsBase):
    __tablename__ = 'host_init_data'
    __table_args__ = ()
    
    host_name = Column(String(255))    #常值
    host_id = Column(String(255))    #常值
    local_cpu_mhz = Column(UnicodeText)    #常值
    physical_cpus = Column(UnicodeText)    #常值
    host_ram = Column(UnicodeText)    #常值
    previous_time = Column(UnicodeText)
    previous_cpu_time = Column(UnicodeText)
    previous_cpu_mhz = Column(UnicodeText)
    previous_host_cpu_time_total = Column(UnicodeText)
    previous_host_cpu_time_busy = Column(UnicodeText)
    previous_overload = Column(UnicodeText)
    host_cpu_overload_threshold = Column(UnicodeText)    #常值
    physical_cpu_mhz = Column(UnicodeText)    #常值
    physical_core_mhz = Column(UnicodeText)    #常值


class HostInitDataTemp(BASE, XdrsBase):
    __tablename__ = 'host_init_data_temp'
    __table_args__ = ()
    
    host_id = Column(String(255))
    previous_host_cpu_time_total = Column(UnicodeText)
    previous_host_cpu_time_busy = Column(UnicodeText)
    physical_cpu_mhz = Column(UnicodeText)