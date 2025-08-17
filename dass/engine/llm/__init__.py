import asyncio
from typing import Optional, Union

from openai.types.chat import ChatCompletion

from ...engine.llm.core import LLM, LLMGenParams
from ..message import Message
from ...config.load import LLMConfig
from ...config.load import load_llm_config

__all__ = [
    "LLM", 
    "LLMGenParams", 
    "init", 
    "generate"
]

_config:Optional[LLMConfig] = None
_llm:Optional[LLM] = None

def init():
    """ llm engine init """

    global _config, _llm
    _config = load_llm_config()
    _llm = LLM(base_url=_config.base_url, api_key=_config.base_url, model=_config.model)

async def generate(prompts:list[Message], params:Optional[LLMGenParams]=None, asynchronous:bool=False) -> Union[str, ChatCompletion]:
    """ generate response from llm 
    using `asynchronous` to control generation is synchronously or not.
    If params is `None` generate will offer a conservative generation parameter.

    Args:
        prompts(list[Message]): messages to pass in llm
        params(Optional[LLMGenParams]): generation parameters of llm. Default to `None`
        asynchronous(Optional[bool]): whether asynchronously generate response. Default to `False`

    Returns:
        Union[str, ChatCompletion]: str if asynchronous == False else ChatCompletion
    """
    global _config, _llm
    if not _config or not _llm:
        raise SystemError("You are using engine.llm.generate invalidly.Suppose you don't init engine.llm.init() before you call engine.llm.generate(...). Please make sure you init engine.llm.")

    if not params:
        params = LLMGenParams(stream=False, temperature=0.8)
    return await _llm.generate(prompts=prompts, params=params, asynchronous=asynchronous)