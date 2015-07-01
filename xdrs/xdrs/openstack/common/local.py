"""Local storage of variables using weak references"""

import threading
import weakref


class WeakLocal(threading.local):
    def __getattribute__(self, attr):
        rval = super(WeakLocal, self).__getattribute__(attr)
        if rval:
            # NOTE(mikal): this bit is confusing. What is stored is a weak
            # reference, not the value itself. We therefore need to lookup
            # the weak reference and return the inner value here.
            rval = rval()
        return rval

    def __setattr__(self, attr, value):
        value = weakref.ref(value)
        return super(WeakLocal, self).__setattr__(attr, value)


# NOTE(mikal): the name "store" should be deprecated in the future
store = WeakLocal()

# A "weak" store uses weak references and allows an object to fall out of scope
# when it falls out of scope in the code that uses the thread local storage. A
# "strong" store will hold a reference to the object so that it never falls out
# of scope.
weak_store = WeakLocal()
strong_store = threading.local()
