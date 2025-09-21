import inspect
import re
from textwrap import dedent
from typing import Any, Optional, Callable, Dict
from enum import Enum
from pydantic import BaseModel
from pydantic import Field

from .parse_type_hint import parse_args_annotation

class ParamProperty(BaseModel):
    """ tool parameters description
    At least one of `type` and `anyOf` should exist in ParamProperty.
    `anyOf` is for `Literal` or `UionType` and meanwhile type is None.
    
    Args:
        type(Optional[str]): parameter type. Default to `None`.
        description(str): describe parameter is what
        additionalProperties(Optional["SubParamProerpty"]): addtional properties for `dict` type. Here camel written is conveinent for converting to json schema
        items(Optional["SubParamProperty"]): item element property for `list or tuple` type. Default to None.
        nullable(Optional[bool]): whether the sub parameter can be null
        anyOf(Optional[list]): allow parameter can be anyone of these types. Default to None.

    Raises:
        ValueError: if `type` and `anyOf` is None at the same time.
    """

    type: Optional[str] = None
    description: str
    additionalProperties: Optional["ParamProperty"] = None
    items: Optional["ParamProperty"] = None
    anyOf: Optional[list] = None
    nullable: Optional[bool] = None

    def model_post_init(self, context):
        if self.type is None and self.anyOf is None:
            raise ValueError("please check your parameters in tool declearation exists at least one of type or anyOf.")

class ToolParameters(BaseModel):
    """ parameters to call tool
     
    Args:
        type(str): "object" is fixed every tool parameters' type is all object
        properties(dict[str, ParamProperty]): param property. `str` is parameter's name and `ParamProperty` is description of the parameter
        required(Optional[list[str]]): contains which parameters should be required. Default to `None`
    """

    type: str = "object"
    properties: dict[str, ParamProperty]
    required: Optional[list[str]] = None

class Tool(BaseModel):
    """ Tool 
    
    Args:
        name(str): tool name
        description(str): tool description
        parameters(Optional[ToolParameters]): parameters for the tool. Default to `None`.
        func(Callable): tool function

    Example:
        ```python
        @tool
        def get_weather(city:str):
            return f"Sunny in {city}."

        weather_tool(city="Shanghai")
        # will output `Sunny in Shanghai`

        weather_tool.to_openai_format_dict()
        # will output a standard openai format prompt
        ```
    """
    
    name: str
    description: str
    parameters: Optional[ToolParameters] = None
    func: Callable = Field(exclude=True)

    def __call__(self, *args, **kwargs):
        try:
            res = self.func(*args, **kwargs)
            return ToolResult(code=ResultFlag.SUCCESS, msg=res)
        except Exception as e:
            return ToolResult(code=ResultFlag.ERROR, msg=e)
    
    def to_openai_format_dict(self):
        return {
            "type": "function",
            "function": self.model_dump(exclude_none=True)
        }

class ResultFlag(Enum):
    SUCCESS = 200
    ERROR = 400
    NOT_ENOUGH_PARAMS = 401
    PARSE_FAILED = 402

class ToolResult(BaseModel):
    code: ResultFlag
    msg: Any

def tool(func:callable):
    """ tool wrapper
    Easily convert a function to a tool using @tool

    Example:
    ```python
    @tool
    def count(a:int, b:int, c:Optional[int]=None):
        \"""count
         
        Args:
            a(int): to add
            b(int): added number
            c(Optional[int]): test Optional type. Default to `None`
        \"""
        return a + b
    
    print(count.model_dump(exclude_none=True))
    # Output
    # {
    #   'name': 'count', 
    #   'description': 'count', 
    #   'parameters': 
    #       {
    #           'type': 'object', 
    #           'properties': 
    #               {
    #                   'a': {'type': 'integer', 'description': 'to add'},
    #                   'b': {'type': 'integer', 'description': 'added number'}, 
    #                   'c': {'type': 'integer', 'description': 'test Optional type. Default to `None`', 'nullable': True}
    #               },
    #           'required': ['a', 'b']
    #       },
    #   'func': <function count at 0x0000023EF3FA5EE0>
    # }     

    ```

    Args:
        func(callable): tool function
    """
    
    tool_name = func.__name__
    docstring:str = func.__doc__
    if not docstring:
        raise ValueError("Check your tool function docstring NOT empty. Please make sure function docstring format valid. You can have a look at `dass/plugins/tools/introduction.md`")

    remove_tabs_docstring:str = dedent(docstring).strip()
    parts = remove_tabs_docstring.split("\n\n", 1)
    if len(parts) < 2:
        raise ValueError("Check your tool function docstring includes function introduction and Args. Please make sure function docstring format valid. You can have a look at `dass/plugins/tools/introduction.md`")

    function_desc = parts[0]
    args_content = dedent(parts[1].replace("Args:", "", 1)).strip()
    pattern = re.compile(r'^\s*(\w+)\(.*?\):\s*(.*?)(?=\n\s*\w+\(|\n*$)', re.MULTILINE | re.DOTALL)
    parsed_params = dict(pattern.findall(args_content.strip()))

    signature:inspect.Signature = inspect.signature(func)
    params_dict = signature.parameters

    # tuple element content
    # (      0       ,                      1                         ,          2           ,              3)
    # (parameter_name, a complex dict to describe parameter properties, parameter description, parameter's default value)
    arguments:list[tuple] = []
    for param_name, param in params_dict.items():
        type_annotation:Dict[str, str|object] = parse_args_annotation(param.annotation)
        default_value = param.default
        arguments.append((param_name, type_annotation, parsed_params[param_name], default_value))
    
    properties:dict[str, ParamProperty] = {}
    required:Optional[list[str]] = []
    for argument in arguments:
        name = argument[0]
        arg_type_parsed = argument[1]
        arg_desc = argument[2]
        arg_default_value = argument[3]
        
        arg_type = arg_type_parsed.get("type", None)
        additional_properties = arg_type_parsed.get("additionalProperties", None)
        items = arg_type_parsed.get("items", None)
        anyOf = arg_type_parsed.get("anyOf", None)
        nullable = arg_type_parsed.get("nullable", None)
        
        if additional_properties:
            additional_properties = ParamProperty(**additional_properties)
        if items:
            items = ParamProperty(**items)

        properties[name] = ParamProperty(
            type=arg_type,
            description=arg_desc,
            additionalProperties=additional_properties,
            items=items,
            anyOf=anyOf,
            nullable=nullable
        )
        
        if arg_default_value is inspect.Parameter.empty:
            required.append(name)
    required = None if len(required) == 0 else required

    return Tool(
        name=tool_name,
        description=function_desc,
        parameters=ToolParameters(
            properties=properties,
            required=required
        ),
        func=func
    )