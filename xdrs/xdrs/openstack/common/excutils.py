"""
Exception related utilities.
"""

import logging
import sys
import traceback
import six

from xdrs.openstack.common.gettextutils import _


class save_and_reraise_exception(object):
    """
    Save current exception, run some code and then re-raise.
    """
    def __init__(self):
        self.reraise = True

    def __enter__(self):
        self.type_, self.value, self.tb, = sys.exc_info()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            logging.error(_('Original exception being dropped: %s'),
                          traceback.format_exception(self.type_,
                                                     self.value,
                                                     self.tb))
            return False
        if self.reraise:
            six.reraise(self.type_, self.value, self.tb)