import asyncio
from typing import Optional, Union

from openai.types.chat import ChatCompletion

from .core import LLM, LLMGenParams
from ..message import Message
from ...config.load import LLMConfig
from ...config.load import load_llm_config

__all__ = [
    "LLM", 
    "LLMGenParams", 
    "init", 
    "generate"
]