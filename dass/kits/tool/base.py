import inspect
import re
from textwrap import dedent
from typing import Any, Optional, Callable
from enum import Enum
from pydantic import BaseModel

class ParamProperty(BaseModel):
    """ tool parameters description
    
    Args:
        type(str): type of parameter
        description(str): describe parameter is what
    """
    type: str
    description: str

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
    func: Callable

    def __call__(self, *args, **kwargs):
        return self.func(*args, *kwargs)
    
    def to_openai_format_dict(self):
        return {
            "type": "function",
            "function": self.model_dump(exclude_none=True)
        }

class ResultFlag(Enum):
    SUCCESS: 200
    ERROR: 400
    NOT_ENOUGH_PARAMS: 401
    PARSE_FAILED: 402

class ToolResult(BaseModel):
    code: ResultFlag
    msg: Any

def tool(func:callable):
    """ tool wrapper
    Convert a function to a tool using @tool
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
    #                   'a': {'type': 'int', 'description': 'to add'}, 
    #                   'b': {'type': 'int', 'description': 'added number'}, 
    #                   'c': {'type': 'Optional', 'description': 'test Optional type. Default to `None`'}
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
    arguments:list[tuple] = []
    for param_name, param in params_dict.items():
        type_annotation = _parse_arg_annotation(param.annotation)
        default_value = param.default
        arguments.append((param_name, type_annotation, parsed_params[param_name], default_value))
    
    properties:dict[str, ParamProperty] = {}
    required:Optional[list[str]] = []
    for argument in arguments:
        name = argument[0]
        arg_type = argument[1]
        arg_desc = argument[2]
        arg_default_value = argument[3]
        
        properties[name] = ParamProperty(type=arg_type, description=arg_desc)
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

def _parse_arg_annotation(annotation) -> str:
    """ parse arg annotation
    Convert simple type or a complex type to a string which contains a plain type string.
    Use annotation.__name__ works well in a simple type. However if type is complex such as List[str | int], Optional[str].
    it's not clear in Optional and List with annotation.__name__.
    """

    s = str(annotation).replace("typing.", "", 1)
    # simple type such as <class 'int'>
    if s.startswith("<class '") and s.endswith("'>"):
        return s[8:-2]
    return s