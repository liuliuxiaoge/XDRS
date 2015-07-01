import abc
import six

from xdrs.openstack.common.gettextutils import _


class AbstractFieldType(six.with_metaclass(abc.ABCMeta, object)):
    @abc.abstractmethod
    def coerce(self, obj, attr, value):
        """This is called to coerce (if possible) a value on assignment.

        This method should convert the value given into the designated type,
        or throw an exception if this is not possible.

        :param:obj: The NovaObject on which an attribute is being set
        :param:attr: The name of the attribute being set
        :param:value: The value being set
        :returns: A properly-typed value
        """
        pass

    @abc.abstractmethod
    def from_primitive(self, obj, attr, value):
        """This is called to deserialize a value.

        This method should deserialize a value from the form given by
        to_primitive() to the designated type.

        :param:obj: The NovaObject on which the value is to be set
        :param:attr: The name of the attribute which will hold the value
        :param:value: The serialized form of the value
        :returns: The natural form of the value
        """
        pass

    @abc.abstractmethod
    def to_primitive(self, obj, attr, value):
        """This is called to serialize a value.

        This method should serialize a value to the form expected by
        from_primitive().

        :param:obj: The NovaObject on which the value is set
        :param:attr: The name of the attribute holding the value
        :param:value: The natural form of the value
        :returns: The serialized form of the value
        """
        pass

    @abc.abstractmethod
    def describe(self):
        """Returns a string describing the type of the field."""
        pass


class FieldType(AbstractFieldType):
    @staticmethod
    def coerce(obj, attr, value):
        return value

    @staticmethod
    def from_primitive(obj, attr, value):
        return value

    @staticmethod
    def to_primitive(obj, attr, value):
        return value

    def describe(self):
        return self.__class__.__name__


class UnspecifiedDefault(object):
    pass


class Field(object):
    def __init__(self, field_type, nullable=False, default=UnspecifiedDefault):
        self._type = field_type
        self._nullable = nullable
        self._default = default

    @property
    def nullable(self):
        return self._nullable

    @property
    def default(self):
        return self._default

    def _null(self, obj, attr):
        if self.nullable:
            return None
        elif self._default != UnspecifiedDefault:
            # NOTE(danms): We coerce the default value each time the field
            # is set to None as our contract states that we'll let the type
            # examine the object and attribute name at that time.
            return self._type.coerce(obj, attr, self._default)
        else:
            raise ValueError(_("Field `%s' cannot be None") % attr)

    def coerce(self, obj, attr, value):
        """Coerce a value to a suitable type.

        This is called any time you set a value on an object, like:

          foo.myint = 1

        and is responsible for making sure that the value (1 here) is of
        the proper type, or can be sanely converted.

        This also handles the potentially nullable or defaultable
        nature of the field and calls the coerce() method on a
        FieldType to actually do the coercion.

        :param:obj: The object being acted upon
        :param:attr: The name of the attribute/field being set
        :param:value: The value being set
        :returns: The properly-typed value
        """
        if value is None:
            return self._null(obj, attr)
        else:
            return self._type.coerce(obj, attr, value)

    def from_primitive(self, obj, attr, value):
        """Deserialize a value from primitive form.

        This is responsible for deserializing a value from primitive
        into regular form. It calls the from_primitive() method on a
        FieldType to do the actual deserialization.

        :param:obj: The object being acted upon
        :param:attr: The name of the attribute/field being deserialized
        :param:value: The value to be deserialized
        :returns: The deserialized value
        """
        if value is None:
            return None
        else:
            return self._type.from_primitive(obj, attr, value)

    def to_primitive(self, obj, attr, value):
        """Serialize a value to primitive form.

        This is responsible for serializing a value to primitive
        form. It calls to_primitive() on a FieldType to do the actual
        serialization.

        :param:obj: The object being acted upon
        :param:attr: The name of the attribute/field being serialized
        :param:value: The value to be serialized
        :returns: The serialized value
        """
        if value is None:
            return None
        else:
            return self._type.to_primitive(obj, attr, value)

    def describe(self):
        """Return a short string describing the type of this field."""
        name = self._type.describe()
        prefix = self.nullable and 'Nullable' or ''
        return prefix + name


class CompoundFieldType(FieldType):
    def __init__(self, element_type, **field_args):
        self._element_type = Field(element_type, **field_args)


class List(CompoundFieldType):
    def coerce(self, obj, attr, value):
        if not isinstance(value, list):
            raise ValueError(_('A list is required here'))
        for index, element in enumerate(list(value)):
            value[index] = self._element_type.coerce(
                    obj, '%s[%i]' % (attr, index), element)
        return value

    def to_primitive(self, obj, attr, value):
        return [self._element_type.to_primitive(obj, attr, x) for x in value]

    def from_primitive(self, obj, attr, value):
        return [self._element_type.from_primitive(obj, attr, x) for x in value]


class Object(FieldType):
    def __init__(self, obj_name, **kwargs):
        self._obj_name = obj_name
        super(Object, self).__init__(**kwargs)

    def coerce(self, obj, attr, value):
        try:
            obj_name = value.obj_name()
        except AttributeError:
            obj_name = ""

        if obj_name != self._obj_name:
            raise ValueError(_('An object of type %s is required here') %
                             self._obj_name)
        return value

    @staticmethod
    def to_primitive(obj, attr, value):
        return value.obj_to_primitive()

    @staticmethod
    def from_primitive(obj, attr, value):
        # FIXME(danms): Avoid circular import from base.py
        from nova.objects import base as obj_base
        return obj_base.NovaObject.obj_from_primitive(value, obj._context)

    def describe(self):
        return "Object<%s>" % self._obj_name


class AutoTypedField(Field):
    AUTO_TYPE = None

    def __init__(self, **kwargs):
        super(AutoTypedField, self).__init__(self.AUTO_TYPE, **kwargs)


class ListOfObjectsField(AutoTypedField):
    def __init__(self, objtype, **kwargs):
        self.AUTO_TYPE = List(Object(objtype))
        super(ListOfObjectsField, self).__init__(**kwargs)
