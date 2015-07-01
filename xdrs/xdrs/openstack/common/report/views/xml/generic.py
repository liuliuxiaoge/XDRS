"""
Provides generic XML views
"""

import collections as col
import copy
import xml.etree.ElementTree as ET

import six

import xdrs.openstack.common.report.utils as utils


class KeyValueView(object):
    """A Key-Value XML View

    This view performs advanced serialization of a data model
    into XML.  It first deserializes any values marked as XML so
    that they can be properly reserialized later.  It then follows
    the following rules to perform serialization:

    key : text/xml
        The tag name is the key name, and the contents are the text or xml
    key : Sequence
        A wrapper tag is created with the key name, and each item is placed
        in an 'item' tag
    key : Mapping
        A wrapper tag is created with the key name, and the serialize is called
        on each key-value pair (such that each key gets its own tag)

    :param str wrapper_name: the name of the top-level element
    """

    def __init__(self, wrapper_name="model"):
        self.wrapper_name = wrapper_name

    def __call__(self, model):
        # this part deals with subviews that were already serialized
        cpy = copy.deepcopy(model)
        for key, valstr in model.items():
            if getattr(valstr, '__is_xml__', False):
                cpy[key] = ET.fromstring(valstr)

        def serialize(rootmodel, rootkeyname):
            res = ET.Element(rootkeyname)

            if isinstance(rootmodel, col.Mapping):
                for key in rootmodel:
                    res.append(serialize(rootmodel[key], key))
            elif (isinstance(rootmodel, col.Sequence)
                    and not isinstance(rootmodel, six.string_types)):
                for val in rootmodel:
                    res.append(serialize(val, 'item'))
            elif ET.iselement(rootmodel):
                res.append(rootmodel)
            else:
                res.text = str(rootmodel)

            return res

        res = utils.StringWithAttrs(ET.tostring(serialize(cpy,
                                                          self.wrapper_name)))
        res.__is_xml__ = True
        return res
