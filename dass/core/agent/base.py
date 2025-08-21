from abc import ABC
from abc import abstractmethod
from typing import Any, Optional
from pydantic import BaseModel

from ...config.load import LLMConfig, EmbeddingConfig
from ...engine import LLM, LLMGenParams, Message
from ...engine import MemoryEngine


class Agent(ABC, BaseModel):
    """ Base agent class
    Every agent need to extend it. Every agent have to be capable to request llm and retrieve memory.
    
    Args:
        llm_config(LLMConfig): llm config in config.toml
        embedding_config(EmbeddingConfig): embedding config in config.toml
        llm(Optional[LLM]): llm. Default to `None`
        llm_gen_params(Optional[LLMGenParams]): llm generation parameters. Default to `None`.
        memory_engine(Optional[MemoryEngine]): memory engine of agent. Default to `None`.
    """

    llm_config:LLMConfig
    embedding_config:EmbeddingConfig
    llm: Optional[LLM] = None
    llm_gen_params: Optional[LLMGenParams] = None
    memory_engine:Optional[MemoryEngine] = None

    class Config:
        arbitrary_types_allowed = True
        extra = "allow"

    def model_post_init(self, context):
        print(f"{self.__class__.__name__} is initializing llm...")
        self.llm = LLM(
            base_url=self.llm_config.base_url,
            api_key=self.llm_config.api_key,
            model=self.llm_config.model
        )
        print(f"{self.__class__.__name__} has been initialized llm!")
        
        print(f"{self.__class__.__name__} is initializing memory engine...")
        self.memory_engine = MemoryEngine(config=self.embedding_config)
        print(f"{self.__class__.__name__} has initialized memory engine!")

    async def __call__(self, *args, **kwargs) -> Any:
        return await self.execute(*args, **kwargs)
    
    @abstractmethod
    async def execute(self, *args, **kwargs) -> Any:
        """ agent core execution """

    @abstractmethod
    def request_llm(message:list[Message]):
        """ request a list of message to llm """

    @abstractmethod
    def retrieve_memory(query:str, top_k:int):
        """ retrieve top_k number most relative memories """