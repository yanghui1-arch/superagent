from typing import get_origin, get_args
from typing import Any, Union, Literal
import types
from copy import copy

_BASE_TYPE_MAPPING = {
    int: {"type": "integer"},
    float: {"type": "number"},
    str: {"type": "string"},
    bool: {"type": "boolean"},
    list: {"type": "array"},
    dict: {"type": "object"},
    Any: {"type": "any"},
    types.NoneType: {"type": "null"},
}

def parse_args_annotation(annotation_hint: type) -> dict[str, str|object]:
    """ parse a type to a standard json schema
    tuple is not supported now and will throw a TypeError
    
    Args:
        annotation_hint(type): annotation type
    
    Returns:
        dict[str, str|object]: {"type": ..., "items": {"type": ...}, "additionalProperties": {"type": ...}, "nullable": ...}
    """

    origin = get_origin(annotation_hint)
    args:tuple = get_args(annotation_hint)

    # base type
    if origin is None:
        if annotation_hint in _BASE_TYPE_MAPPING:
            return copy(_BASE_TYPE_MAPPING[annotation_hint])
        return {"type": "object"}
    
    # generic type
    elif origin is Union or (hasattr(types, "UnionType") and origin is types.UnionType):
        return _parse_union(args)

    elif origin is list:
        if not args:
            return {"type": "array"}
        else:
            # the element type of list should be only one.
            return {"type": "array", "items": parse_args_annotation(args[0])}
    
    # not support tuple type
    elif origin is tuple:
        raise TypeError("It doesn't support tuple now. You can PR for complete it. It's in dass/kits/tool/parse_utils.py line 50.")
    
    elif origin is dict:
        out = {"type": "object"}
        if len(args) == 2:
            out["additionalProperties"] = parse_args_annotation(args[1])
        return out
    
    elif origin is Literal:
        literal_types = set(type(arg) for arg in args)
        final_type = _parse_union(literal_types)
        final_type.update({"enum": [arg for arg in args if arg is not None]})
        return final_type
    

def _parse_union(args: tuple[Any, ...]) -> dict:# 
    """ parse union type
    If args includes only one not None type return it directly
    else args includes at least one complex type then return {"anyOf": ...}

    Args:
        args(tuple[Any, ...]): union arguments

    Returns:
        dict: a sub parameter property json schema dict.
    """

    subtypes = [parse_args_annotation(t) for t in args if t is not type(None)]
    if len(subtypes) == 1:
        return_dict = subtypes[0]
    else:
        return_dict = {"anyOf": subtypes}
    if type(None) in args:
        return_dict["nullable"] = True
    return return_dict