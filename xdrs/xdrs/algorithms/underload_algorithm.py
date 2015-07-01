"""
实现三种简单的欠载检测算法；
1.认为主机是欠载的算法；
2.实现单阈值欠载检测算法；
3.实现平均阈值欠载检测算法；
"""

from contracts import contract

import logging
log = logging.getLogger(__name__)


@contract
def always_underloaded_factory(time_step, migration_time, params):
    """ 
    实现一个算法，总是认为主机是欠载的；
    参数：（为了统一接口，简单算法中不会应用，开发复杂的算法，则会应用，复杂算法这里没有给出；）
    time_step：调用算法的时间长度；
    migration_time：所计算出的虚拟机迁移所花费的时间；
    params：若干参数信息；
    """
    return lambda utilization, state=None: (True, {})


@contract
def threshold_factory(time_step, migration_time, params):
    """ 
    实现单阈值欠载检测算法；
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
    实现平均阈值欠载检测算法；
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
    静态的基于阈值的欠载检测算法；
    如果最近一个主机CPU利用率的值低于指定的阈值，则算法返回值为True，
    认为被检测的主机是欠载的；
    """
    if utilization:
        return utilization[-1] <= threshold
    return False


@contract
def last_n_average_threshold(threshold, n, utilization):
    """ 
    平均的静态基于阈值的欠载检测算法；

    如果最近N个主机CPU利用率的平均值低于指定的阈值，则算法返回值为True，
    认为被检测的主机是欠载的；
    """
    if utilization:
        utilization = utilization[-n:]
        return sum(utilization) / len(utilization) <= threshold
    return False