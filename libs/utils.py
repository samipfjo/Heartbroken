import typing


class _NoWrite(type):
    """
    Custom type for use as a metaclass that prevents writing class attributes
    """
    def __setattr__(cls, name, _):
        raise TypeError(f'Cannot set class property "{name}": this is a static class')

# ====
class StaticClass (metaclass=_NoWrite):
    """
    Provides the ability to make a class static by subclassing this class.
    Static in this case means that attributes cannot be set on the class,
    nor can it be initialized (will raise a TypeError in either case)
    """
    def __init__(self):
        raise TypeError(f'{type(self).__name__} is a static class')

# ========
def _DEEP_GET_FAIL(): pass  # Arbitrary unused object for comparison
def _deep_get(dictionary: typing.Union[dict, None],
              keys: typing.Iterable, default: typing.Any = None) -> typing.Any:
    """
    Dig into a dictionary following the iterable of keys.
    Safely handles non-existant gets as well as the dictionary itself being None.
    Return :default if it fails at any point in its journey, otherwise return result.
    """

    if type(dictionary) != dict:
        return default

    result = dictionary
    for key in keys:
        # cython hates walruses :(
        result = result.get(key, _DEEP_GET_FAIL)
        if result == _DEEP_GET_FAIL:
            return default

    return result
