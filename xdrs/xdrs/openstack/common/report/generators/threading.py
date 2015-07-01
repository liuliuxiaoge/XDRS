"""
Provides thread-related generators
"""

import sys

import greenlet

import xdrs.openstack.common.report.models.threading as tm
from xdrs.openstack.common.report.models import with_default_views as mwdv
import xdrs.openstack.common.report.utils as rutils
import xdrs.openstack.common.report.views.text.generic as text_views


class ThreadReportGenerator(object):
    """
    A Thread Data Generator
    """

    def __call__(self):
        threadModels = [
            tm.ThreadModel(thread_id, stack)
            for thread_id, stack in sys._current_frames().items()
        ]

        thread_pairs = dict(zip(range(len(threadModels)), threadModels))
        return mwdv.ModelWithDefaultViews(thread_pairs,
                                          text_view=text_views.MultiView())



class GreenThreadReportGenerator(object):
    """
    A Green Thread Data Generator
    """

    def __call__(self):
        threadModels = [
            tm.GreenThreadModel(gr.gr_frame)
            for gr in rutils._find_objects(greenlet.greenlet)
        ]

        thread_pairs = dict(zip(range(len(threadModels)), threadModels))
        return mwdv.ModelWithDefaultViews(thread_pairs,
                                          text_view=text_views.MultiView())
