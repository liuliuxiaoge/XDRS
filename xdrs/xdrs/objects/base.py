"""Xdrs common internal object model"""

import collections
import functools

import netaddr
from oslo import messaging
import six

from xdrs import exception
from xdrs.objects import fields
from xdrs.openstack.common.gettextutils import _
from xdrs.openstack.common import log as logging


LOG = logging.getLogger('object')


class NotSpecifiedSentinel:
    pass


def get_attrname(name):
    """
    Return the mangled name of the attribute's underlying storage.
    """
    return '_%s' % name


def make_class_properties(cls):
    cls.fields = dict(cls.fields)
    for supercls in cls.mro()[1:-1]:
        if not hasattr(supercls, 'fields'):
            continue
        for name, field in supercls.fields.items():
            if name not in cls.fields:
                cls.fields[name] = field
    for name, field in cls.fields.iteritems():

        def getter(self, name=name):
            attrname = get_attrname(name)
            if not hasattr(self, attrname):
                self.obj_load_attr(name)
            return getattr(self, attrname)

        def setter(self, value, name=name, field=field):
            self._changed_fields.add(name)
            try:
                return setattr(self, get_attrname(name),
                               field.coerce(self, name, value))
            except Exception:
                attr = "%s.%s" % (self.obj_name(), name)
                LOG.exception(_('Error setting %(attr)s') %
                              {'attr': attr})
                raise

        setattr(cls, name, property(getter, setter))


class XdrsObjectMetaclass(type):
    """
    Metaclass that allows tracking of object classes.
    """
    indirection_api = None

    def __init__(cls, names, bases, dict_):
        if not hasattr(cls, '_obj_classes'):
            cls._obj_classes = collections.defaultdict(list)
        else:
            make_class_properties(cls)
            cls._obj_classes[cls.obj_name()].append(cls)


def remotable_classmethod(fn):
    """
    Decorator for remotable classmethods.
    """
    @functools.wraps(fn)
    def wrapper(cls, context, *args, **kwargs):
        if XdrsObject.indirection_api:
            result = XdrsObject.indirection_api.object_class_action(
                context, cls.obj_name(), fn.__name__, cls.VERSION,
                args, kwargs)
        else:
            result = fn(cls, context, *args, **kwargs)
            if isinstance(result, XdrsObject):
                result._context = context
        return result
    return classmethod(wrapper)


@six.add_metaclass(XdrsObjectMetaclass)
class XdrsObject(object):
    """
    Base class and object factory.
    """

    VERSION = '1.0'

    fields = {}
    obj_extra_fields = []

    def __init__(self, context=None, **kwargs):
        self._changed_fields = set()
        self._context = context
        for key in kwargs.keys():
            self[key] = kwargs[key]

    @classmethod
    def obj_name(cls):
        """
        Return a canonical name for this object which will be used over
        the wire for remote hydration.
        """
        return cls.__name__

    @classmethod
    def obj_class_from_name(cls, objname, objver):
        """
        Returns a class from the registry based on a name and version.
        """
        if objname not in cls._obj_classes:
            LOG.error(_('Unable to instantiate unregistered object type '
                        '%(objtype)s') % dict(objtype=objname))
            raise exception.UnsupportedObjectError(objtype=objname)

        latest = None
        compatible_match = None
        for objclass in cls._obj_classes[objname]:
            if objclass.VERSION == objver:
                return objclass

            version_bits = tuple([int(x) for x in objclass.VERSION.split(".")])
            if latest is None:
                latest = version_bits
            elif latest < version_bits:
                latest = version_bits

        if compatible_match:
            return compatible_match

        latest_ver = '%i.%i' % latest
        raise exception.IncompatibleObjectVersion(objname=objname,
                                                  objver=objver,
                                                  supported=latest_ver)

    @classmethod
    def _obj_from_primitive(cls, context, objver, primitive):
        self = cls()
        self._context = context
        self.VERSION = objver
        objdata = primitive['xdrs_object.data']
        changes = primitive.get('xdrs_object.changes', [])
        for name, field in self.fields.items():
            if name in objdata:
                setattr(self, name, field.from_primitive(self, name,
                                                         objdata[name]))
        self._changed_fields = set([x for x in changes if x in self.fields])
        return self

    @classmethod
    def obj_from_primitive(cls, primitive, context=None):
        """
        Object field-by-field hydration.
        """
        if primitive['xdrs_object.namespace'] != 'xdrs':
            # NOTE(danms): We don't do anything with this now, but it's
            # there for "the future"
            raise exception.UnsupportedObjectError(
                objtype='%s.%s' % (primitive['xdrs_object.namespace'],
                                   primitive['xdrs_object.name']))
        objname = primitive['xdrs_object.name']
        objver = primitive['xdrs_object.version']
        objclass = cls.obj_class_from_name(objname, objver)
        return objclass._obj_from_primitive(context, objver, primitive)

    def obj_make_compatible(self, primitive, target_version):
        pass

    def obj_to_primitive(self, target_version=None):
        """
        Simple base-case dehydration.
        """
        primitive = dict()
        for name, field in self.fields.items():
            if self.obj_attr_is_set(name):
                primitive[name] = field.to_primitive(self, name,
                                                     getattr(self, name))
        if target_version:
            self.obj_make_compatible(primitive, target_version)
        obj = {'xdrs_object.name': self.obj_name(),
               'xdrs_object.namespace': 'xdrs',
               'xdrs_object.version': target_version or self.VERSION,
               'xdrs_object.data': primitive}
        if self.obj_what_changed():
            obj['xdrs_object.changes'] = list(self.obj_what_changed())
        return obj

    def obj_load_attr(self, attrname):
        """
        Load an additional attribute from the real object.
        """
        raise NotImplementedError(
            _("Cannot load '%s' in the base class") % attrname)

    def save(self, context):
        """
        Save the changed fields back to the store.
        """
        raise NotImplementedError('Cannot save anything in the base class')

    def obj_what_changed(self):
        """
        Returns a set of fields that have been modified.
        """
        changes = set(self._changed_fields)
        for field in self.fields:
            if (self.obj_attr_is_set(field) and
                    isinstance(self[field], XdrsObject) and
                    self[field].obj_what_changed()):
                changes.add(field)
        return changes

    def obj_get_changes(self):
        """
        Returns a dict of changed fields and their new values.
        """
        changes = {}
        for key in self.obj_what_changed():
            changes[key] = self[key]
        return changes

    def obj_reset_changes(self, fields=None):
        """
        Reset the list of fields that have been changed.
        """
        if fields:
            self._changed_fields -= set(fields)
        else:
            self._changed_fields.clear()

    def obj_attr_is_set(self, attrname):
        """
        Test object to see if attrname is present.
        """
        if attrname not in self.obj_fields:
            raise AttributeError(
                _("%(objname)s object has no attribute '%(attrname)s'") %
                {'objname': self.obj_name(), 'attrname': attrname})
        return hasattr(self, get_attrname(attrname))

    @property
    def obj_fields(self):
        return self.fields.keys() + self.obj_extra_fields


    def iteritems(self):
        """
        For backwards-compatibility with dict-based objects.
        """
        for name in self.obj_fields:
            if (self.obj_attr_is_set(name) or
                    name in self.obj_extra_fields):
                yield name, getattr(self, name)

    items = lambda self: list(self.iteritems())

    def __getitem__(self, name):
        """
        For backwards-compatibility with dict-based objects.
        """
        return getattr(self, name)

    def __setitem__(self, name, value):
        """
        For backwards-compatibility with dict-based objects.
        """
        setattr(self, name, value)

    def __contains__(self, name):
        """
        For backwards-compatibility with dict-based objects.
        """
        try:
            return self.obj_attr_is_set(name)
        except AttributeError:
            return False

    def get(self, key, value=NotSpecifiedSentinel):
        """
        For backwards-compatibility with dict-based objects.
        """
        if key not in self.obj_fields:
            raise AttributeError("'%s' object has no attribute '%s'" % (
                    self.__class__, key))
        if value != NotSpecifiedSentinel and not self.obj_attr_is_set(key):
            return value
        else:
            return self[key]

    def update(self, updates):
        """
        For backwards-compatibility with dict-base objects.
        """
        for key, value in updates.items():
            self[key] = value


class ObjectListBase(object):
    """
    Mixin class for lists of objects.
    """
    fields = {
        'objects': fields.ListOfObjectsField('XdrsObject'),
        }

    child_versions = {}

    def __iter__(self):
        """List iterator interface."""
        return iter(self.objects)

    def __len__(self):
        """List length."""
        return len(self.objects)

    def __getitem__(self, index):
        """List index access."""
        if isinstance(index, slice):
            new_obj = self.__class__()
            new_obj.objects = self.objects[index]
            new_obj.obj_reset_changes()
            new_obj._context = self._context
            return new_obj
        return self.objects[index]

    def __contains__(self, value):
        """List membership test."""
        return value in self.objects

    def count(self, value):
        """List count of value occurrences."""
        return self.objects.count(value)

    def index(self, value):
        """List index of value."""
        return self.objects.index(value)

    def sort(self, cmp=None, key=None, reverse=False):
        self.objects.sort(cmp=cmp, key=key, reverse=reverse)

    def _attr_objects_to_primitive(self):
        """Serialization of object list."""
        return [x.obj_to_primitive() for x in self.objects]

    def _attr_objects_from_primitive(self, value):
        """Deserialization of object list."""
        objects = []
        for entity in value:
            obj = XdrsObject.obj_from_primitive(entity, context=self._context)
            objects.append(obj)
        return objects

    def obj_make_compatible(self, primitive, target_version):
        primitives = primitive['objects']
        child_target_version = self.child_versions.get(target_version, '1.0')
        for index, item in enumerate(self.objects):
            self.objects[index].obj_make_compatible(
                primitives[index]['xdrs_object.data'],
                child_target_version)
            primitives[index]['xdrs_object.version'] = child_target_version

    def obj_what_changed(self):
        changes = set(self._changed_fields)
        for child in self.objects:
            if child.obj_what_changed():
                changes.add('objects')
        return changes


"""
注：内部方法需要进行进一步的分析修正；
"""
class XdrsObjectSerializer(messaging.NoOpSerializer):
    @property
    def conductor(self):
        if not hasattr(self, '_conductor'):
            from xdrs.conductor import api as conductor_api
            self._conductor = conductor_api.API()
        return self._conductor

    def _process_object(self, context, objprim):
        try:
            objinst = XdrsObject.obj_from_primitive(objprim, context=context)
        except exception.IncompatibleObjectVersion as e:
            objinst = self.conductor.object_backport(context, objprim,
                                                     e.kwargs['supported'])
        return objinst

    def _process_iterable(self, context, action_fn, values):
        """
        Process an iterable, taking an action on each value.
        """
        iterable = values.__class__
        if iterable == set:
            iterable = tuple
        return iterable([action_fn(context, value) for value in values])

    def serialize_entity(self, context, entity):
        if isinstance(entity, (tuple, list, set)):
            entity = self._process_iterable(context, self.serialize_entity,
                                            entity)
        elif (hasattr(entity, 'obj_to_primitive') and
              callable(entity.obj_to_primitive)):
            entity = entity.obj_to_primitive()
        return entity

    def deserialize_entity(self, context, entity):
        if isinstance(entity, dict) and 'xdrs_object.name' in entity:
            entity = self._process_object(context, entity)
        elif isinstance(entity, (tuple, list, set)):
            entity = self._process_iterable(context, self.deserialize_entity,
                                            entity)
        return entity


def obj_to_primitive(obj):
    if isinstance(obj, ObjectListBase):
        return [obj_to_primitive(x) for x in obj]
    elif isinstance(obj, XdrsObject):
        result = {}
        for key, value in obj.iteritems():
            result[key] = obj_to_primitive(value)
        return result
    elif isinstance(obj, netaddr.IPAddress):
        return str(obj)
    elif isinstance(obj, netaddr.IPNetwork):
        return str(obj)
    else:
        return obj