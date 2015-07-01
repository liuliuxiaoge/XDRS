"""
Various utilities for report generation

This module includes various utilities
used in generating reports.
"""

import gc


class StringWithAttrs(str):
    """
    A String that can have arbitrary attributes
    """

    pass


def _find_objects(t):
    """
    Find Objects in the GC State
    """

    return [o for o in gc.get_objects() if isinstance(o, t)]