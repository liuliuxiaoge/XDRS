"""
Provides a way to generate serializable reports

This package/module provides mechanisms for defining reports
which may then be serialized into various data types.  Each
report ( :class:`openstack.common.report.report.BasicReport` )
is composed of one or more report sections
( :class:`openstack.common.report.report.BasicSection` ),
which contain generators which generate data models
( :class:`openstack.common.report.models.base.ReportModels` ),
which are then serialized by views.
"""
