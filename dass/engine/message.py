import json
from typing import Literal, Union, Optional
from pydantic import BaseModel
from openai.types.chat.chat_completion_message_tool_call import Function
from openai.types.chat.chat_completion_message_function_tool_call import ChatCompletionMessageFunctionToolCall


class MultiModalitySchema(BaseModel):
    """ MultiModality schema 
    text is neccessary while type is `text` and image_url is neccessary while type is `image_url`
    """

    type: Literal["text", "image_url", "input_audio", "video", "video_url"]
    text: Optional[str]
    image_url: Optional[dict]
    input_audio: Optional[dict]
    video: Optional[list]
    video_url: Optional[dict]

    @classmethod
    def text_mm_schema(cls, text: str):
        """ text schema in multimodality 
        
        Args:
            text(str): only text content

        Returns:
            MultimodalitySchema: text multimodality schema.
        """

        return MultiModalitySchema("text", text=text)
    
    @classmethod
    def image_url_mm_schema(cls, image_url: dict):
        """ image schema in multimodality
        url in image_url can be a base64 or a url

        Args:
            image_url(dict): include only one key `url`

        Returns:
            MultimodalitySchema: image url multimodality schema.

        Raises:
            KeyError: when image_url exclude `url` or key number exceeds 1
        """

        keys = list(image_url.keys())
        if len(keys) == 1 and keys[0] == "url":
            return MultiModalitySchema("image_url", image_url=image_url)
        raise KeyError("image_url parameter should be one key and the key name is url in multimodality. Please ensure your image_url is valid.")

    @classmethod
    def input_audio_mm_schema(cls, input_audio:dict):
        """ input audio schema in multimodality
        
        Args:
            input_audio(dict): include two keys, one is `data` another is `format` which tells the audio format
        
        Returns:
            MultimodalitySchema: input audio multimodality schema.

        Raises:
            KeyError: when input_audio key number not euqual to 2 or exclude one of `data` and `format`
        """

        keys = list(input_audio.keys())
        if (len(keys) == 2 and 'data' in keys and 'format' in keys):
            return MultiModalitySchema('input_audio', input_audio=input_audio)
        raise KeyError("input_audio parameter should only include two keys and one is `data` another is `format`. Please make sure your input_audio parameter is valid.")
    
    @classmethod
    def video_mm_schema(cls, video:list):
        """ video schema in multimodality """
        return MultiModalitySchema('video', video=video)
    
    @classmethod
    def video_url_mm_schema(cls, video_url:dict):
        """ video_url schema in multimodality
        
        Args:
            video_url(dict): include one key `url`

        Returns:
            MultimodalitySchema: video url multimodality schema.

        Raises:
            KeyError: when video_url key number doesn't equal to 1 or `url` is not in video_url
        """

        keys = list(video_url.keys())
        if (len(keys) == 1 and keys[0] == "url"):
            return MultiModalitySchema("video_url", video_url=video_url)
        raise KeyError("video_url parmater should only include one parameter `url`. please make sure video_url parameter is valid.")

class ParsedToolFunction(BaseModel):
    """ parsed tool function 
    
    Args:
        tool_call_id(str): function calling tool id through completion.choices[0].message.tool_calls[0].id.
        name(str): to be called function name
        arguments(dict): arguments to be passed in `name` function in a json format.
    """

    tool_call_id:str
    name: str
    arguments: dict

class Message(BaseModel):
    role: Literal["user", "assistant", "system", "tool"]
    content: Optional[Union[str, list[MultiModalitySchema]]] = None
    partial: Optional[bool] = None
    tool_calls: Optional[list[ChatCompletionMessageFunctionToolCall]] = None
    tool_call_id: Optional[str] = None

    @classmethod
    def user_message(cls, content: Union[str, list[MultiModalitySchema]]):
        return cls(role='user', content=content)
    
    @classmethod
    def assistant_message(cls, content:Optional[str]=None, partial:Optional[bool]=None, tool_calls:list[ChatCompletionMessageFunctionToolCall]=None):
        return cls(role="assistant", content=content, partial=partial, tool_calls=tool_calls)
    
    @classmethod
    def system_message(cls, content: str):
        return cls(role="system", content=content)
    
    @classmethod
    def tool_message(cls, content: str, tool_call_id:Optional[str]=None):
        return cls(role="tool", content=content, tool_call_id=tool_call_id)
    
def convert_args_to_json(tool_call_id: str, func_name: str, args: str) -> Optional[ParsedToolFunction]:
    """ parse ToolFunction to ParsedToolFunction
    
    Args:
        tool_call_id(str): calling tool function id.
        func_name(str): calling function name
        args(str): a args string in openai Function type. Probably it's not a standard json.

    Returns:
        Optional[ParsedToolFunction]: parsed tool function. If None means parsed failed.
    """
    try:
        parsed_args:dict = json.loads(args)
        return ParsedToolFunction(tool_call_id=tool_call_id, name=func_name, arguments=parsed_args)
    except json.JSONDecodeError as jde:
        print(f"Failed to decode arguments {args} of function {func_name}. Please make the arguments is a valid json string.")
        return None