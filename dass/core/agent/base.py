from abc import ABC
from abc import abstractmethod
from typing import Any, Optional
from pydantic import BaseModel

from ...config.load import LLMConfig, EmbeddingConfig
from ...engine import LLM, LLMGenParams, Message
from ...engine import MemoryEngine
from ...context import MessageContextEngine


class Agent(ABC, BaseModel):
    """ Base agent class
    Every agent need to extend it. Every agent have to be capable to request llm and retrieve memory.
    llm generation parameter will be set (temperature=0.9, stream=False) when you don't give llm_gen_params during initializing agent. 
    
    Args:
        llm_config(LLMConfig): llm config in config.toml
        embedding_config(EmbeddingConfig): embedding config in config.toml
        llm(LLM): llm
        llm_gen_params(Optional[LLMGenParams]): llm generation parameters. Default to `None`.
        memory_engine(Optional[MemoryEngine]): memory engine of agent. Default to `None`.
        context_manager(ContextEngine): manager llm context
    """

    llm_config:LLMConfig
    embedding_config:Optional[EmbeddingConfig] = None
    llm_gen_params: Optional[LLMGenParams] = None

    class Config:
        arbitrary_types_allowed = True
        extra = "allow"

    def model_post_init(self, context):
        if self.llm_gen_params is None:
            print(f"{self.__class__.__name__} is not given a generation parameter. Set default generation parameters to her.")
            self.llm_gen_params = LLMGenParams(stream=False, temperature=0.9)

        print(f"{self.__class__.__name__} is initializing llm...")
        self.llm = LLM(
            base_url=self.llm_config.base_url,
            api_key=self.llm_config.api_key,
            model=self.llm_config.model
        )
        print(f"{self.__class__.__name__} has been initialized llm!")
        
        if self.embedding_config:
            print(f"{self.__class__.__name__} is initializing memory engine...")
            self.memory_engine = MemoryEngine(config=self.embedding_config)
            print(f"{self.__class__.__name__} has initialized memory engine!")
        else:
            print(f"{self.__class__.__name__} doesn't need a memory system.")
        
        self.context_manager = MessageContextEngine(llm_config=self.llm_config)

    async def __call__(self, *args, **kwargs) -> Any:
        return await self.run(*args, **kwargs)
    
    @abstractmethod
    async def run(self, *args, **kwargs) -> Any:
        """ agent core execution """

    @abstractmethod
    def request_llm(message:list[Message]):
        """ request a list of message to llm """

    @abstractmethod
    def retrieve_memory(query:str, top_k:int):
        """ retrieve top_k number most relative memories """