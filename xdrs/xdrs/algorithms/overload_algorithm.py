"""
实现三种简单的过载检测算法；
1.永远不认为主机是过载的算法；
2.静CPU利用率阈值算法；
3.平均CPU利用率阈值算法；
"""

from contracts import contract

import logging
log = logging.getLogger(__name__)


@contract
def never_overloaded_factory(time_step, migration_time, params):
    """ 
    实现一个过载检测算法，其永远不认为主机是过载的；
    参数：（为了统一接口，简单算法中不会应用，开发复杂的算法，则会应用，复杂算法这里没有给出；）
    time_step：调用算法的时间长度；
    migration_time：所计算出的虚拟机迁移所花费的时间；
    params：若干参数信息；
    """
    return lambda utilization, state=None: (False, {})


@contract
def threshold_factory(time_step, migration_time, params):
    """ 
    静态CPU利用率阈值算法的实现；
    参数：（为了统一接口，简单算法中不会应用，开发复杂的算法，则会应用，复杂算法这里没有给出；）
    time_step：调用算法的时间长度；
    migration_time：所计算出的虚拟机迁移所花费的时间；
    params：若干参数信息；
    """
    return lambda utilization, state=None: (threshold(params['threshold'],
                                                      utilization),
                                            {})


@contract
def last_n_average_threshold_factory(time_step, migration_time, params):
    """ 
    平均CPU利用率阈值算法的实现；
    参数：（为了统一接口，简单算法中不会应用，开发复杂的算法，则会应用，复杂算法这里没有给出；）
    time_step：调用算法的时间长度；
    migration_time：所计算出的虚拟机迁移所花费的时间；
    params：若干参数信息；
    """
    return lambda utilization, state=None: (
        last_n_average_threshold(params['threshold'],
                                 params['n'],
                                 utilization),
        {})


@contract
def threshold(threshold, utilization):
    """ 
    静态CPU利用率阈值算法；
    """
    if utilization:
        return utilization[-1] > threshold
    return False


@contract
def last_n_average_threshold(threshold, n, utilization):
    """ 
    平均CPU利用率阈值算法；
    """
    if utilization:
        utilization = utilization[-n:]
        return sum(utilization) / len(utilization) > threshold
    return False