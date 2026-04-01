"""Pytest configuration: stub out homeassistant so calculator tests run without HA installed."""

import sys
import types


class _StubGeneric:
    """Proxy returned by __class_getitem__ so stubs can be used as generic base classes."""

    def __init__(self, origin):
        self._origin = origin

    def __mro_entries__(self, bases):
        # When used as `class Foo(SomeStub[T])`, inject `object` as the base
        return (object,)


class _Stub(types.ModuleType):
    """A module stub that returns itself for any attribute access."""

    def __getattr__(self, name):
        # Return a class/callable stub for anything not found
        child_name = f"{self.__name__}.{name}"
        if child_name not in sys.modules:
            child = _Stub(child_name)
            sys.modules[child_name] = child
            object.__setattr__(self, name, child)
        return sys.modules[child_name]

    def __call__(self, *args, **kwargs):
        return self

    def __bool__(self):
        return True

    def __class_getitem__(cls, item):
        # Return an object that can be used as a base class
        return _StubGeneric(cls)

    def __getitem__(self, item):
        return _StubGeneric(self)

    def __mro_entries__(self, bases):
        return (object,)


def _stub(dotted: str) -> _Stub:
    parts = dotted.split(".")
    for i in range(1, len(parts) + 1):
        name = ".".join(parts[:i])
        if name not in sys.modules:
            mod = _Stub(name)
            sys.modules[name] = mod
            if i > 1:
                parent_name = ".".join(parts[: i - 1])
                setattr(sys.modules[parent_name], parts[i - 1], mod)
    return sys.modules[dotted]  # type: ignore[return-value]


# Stub every homeassistant subpath that the package imports
_stub("homeassistant")
_stub("homeassistant.config_entries")
_stub("homeassistant.core")
_stub("homeassistant.helpers")
_stub("homeassistant.helpers.device_registry")
_stub("homeassistant.helpers.update_coordinator")
_stub("homeassistant.helpers.entity_platform")
_stub("homeassistant.helpers.entity")
_stub("homeassistant.components")
_stub("homeassistant.components.sensor")
_stub("homeassistant.const")
