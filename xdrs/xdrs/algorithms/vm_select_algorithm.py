"""
实现四种简单的虚拟机实例选取算法；
1.随机选取虚拟机实例算法的实现；
2.基于资源最小利用率的虚拟机实例选取算法实现；
3.基于最小迁移时间的虚拟机选取算法的实现；
4.基于最小迁移时间和最大CPU使用的虚拟机实例选取算法的实现；
"""

from contracts import contract
from random import choice
import operator
import logging

log = logging.getLogger(__name__)


@contract
def random_factory(time_step, migration_time, params):
    """ 
    随机选取虚拟机算法的实现；
    参数：（为了统一接口，简单算法中不会应用，开发复杂的算法，则会应用，复杂算法这里没有给出；）
    time_step：调用算法的时间长度；
    migration_time：所计算出的虚拟机迁移所花费的时间；
    params：若干参数信息；
    """
    """
    random:随机选取虚拟机算法；
    """
    return lambda vms_cpu, vms_ram, state=None: ([random(vms_cpu)], {})


@contract
def minimum_utilization_factory(time_step, migration_time, params):
    """ 
    基于资源最小利用率的虚拟机选取算法的实现；
    参数：（为了统一接口，简单算法中不会应用，开发复杂的算法，则会应用，复杂算法这里没有给出；）
    time_step：调用算法的时间长度；
    migration_time：所计算出的虚拟机迁移所花费的时间；
    params：若干参数信息；
    """
    """
    minimum_utilization:基于最小CPU利用率的虚拟机选取算法；
    """
    return lambda vms_cpu, vms_ram, state=None: \
        ([minimum_utilization(vms_cpu)], {})


@contract
def minimum_migration_time_factory(time_step, migration_time, params):
    """ 
    基于最小迁移时间的虚拟机选取算法的实现；
    参数：（为了统一接口，简单算法中不会应用，开发复杂的算法，则会应用，复杂算法这里没有给出；）
    time_step：调用算法的时间长度；
    migration_time：所计算出的虚拟机迁移所花费的时间；
    params：若干参数信息；
    """
    """
    minimum_migration_time:基于最小RAM使用(表示虚拟机迁移的时间将会最少)的虚拟机选取算法；
    """
    return lambda vms_cpu, vms_ram, state=None: \
        ([minimum_migration_time(vms_ram)], {})


@contract
def minimum_migration_time_max_cpu_factory(time_step, migration_time, params):
    """ 
    基于最小迁移时间和最大CPU使用的虚拟机选取算法的实现；
    参数：（为了统一接口，简单算法中不会应用，开发复杂的算法，则会应用，复杂算法这里没有给出；）
    time_step：调用算法的时间长度；
    migration_time：所计算出的虚拟机迁移所花费的时间；
    params：若干参数信息；
    """
    """
    minimum_migration_time_max_cpu:应用最小RAM和最大CPU使用的选取虚拟机算法；
    """
    return lambda vms_cpu, vms_ram, state=None: \
        ([minimum_migration_time_max_cpu(params['last_n'],
                                         vms_cpu,
                                         vms_ram)], {})


@contract
def minimum_migration_time(vms_ram):
    """ 
    基于最小RAM使用(表示虚拟机迁移的时间将会最少)的虚拟机选取算法；
    """
    min_index, min_value = min(enumerate(vms_ram.values()),
                               key=operator.itemgetter(1))
    return vms_ram.keys()[min_index]


@contract
def minimum_utilization(vms_cpu):
    """ 
    基于最小CPU利用率的虚拟机选取算法；
    """
    last_utilization = [x[-1] for x in vms_cpu.values()]
    min_index, min_value = min(enumerate(last_utilization),
                               key=operator.itemgetter(1))
    return vms_cpu.keys()[min_index]


@contract
def random(vms_cpu):
    """ 
    随机选取虚拟机算法；
    """
    return choice(vms_cpu.keys())


@contract
def minimum_migration_time_max_cpu(last_n, vms_cpu, vms_ram):
    """ 
    应用最小RAM和最大CPU使用的选取虚拟机算法；
    """
    min_ram = min(vms_ram.values())
    max_cpu = 0
    selected_vm = None
    for vm, cpu in vms_cpu.items():
        if vms_ram[vm] > min_ram:
            continue
        vals = cpu[-last_n:]
        avg = float(sum(vals)) / len(vals)
        if max_cpu < avg:
            max_cpu = avg
            selected_vm = vm
    return selected_vm