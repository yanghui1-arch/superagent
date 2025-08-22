from abc import ABC
from abc import abstractmethod
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel
from uuid import UUID
from dass.engine.message import Message
from ._prompt import extract_prompt
from ._prompt import START_EXTRACTION_TAG, NO_RELATED_EXTRACTION_TAG
from ..config.load import LLMConfig
from ..engine.llm import LLM, LLMGenParams
from dass.error import ParseError

# Message or Memory
Context = Message

class ContextEngine(BaseModel, ABC):
    """ ContextEngine manages conversations with llm. """
    context:dict[UUID, list[Message]] = {}

    class Config:
        extra = "allow"

    @abstractmethod
    def compress(self):
        raise NotImplementedError("Please implement compress function of ContextEngine")

    @abstractmethod
    def extract(self):
        raise NotImplementedError("Please implement extract function of ContextEngine")

    @abstractmethod
    def append(self, args, **kwargs):
        raise NotImplementedError("Please implement append function of ContextEngine")

class ExtractResult(BaseModel):
    """ extract result 
    
    Args:
        relative(bool): whether extraction is relative to query
        message(str): relative messages if relative is true else it's llm reason for considering why conversations are all not relative to query. 
    """

    relative: bool
    message: str

class MessageContextEngine(ContextEngine):
    """ Message context engine focus on management about message.
    Its main task is to record active round conversation with llm and store the messages with various strategies.

    Args:
        context(Dict[UUID, List[Message]]): record all messages for every conversation.
        llm_config(LLMConfig): llm config
        llm_gen_param(Optional[LLMGenParams]): llm generation parameters. Default to None.
    """

    llm_config: LLMConfig
    llm_gen_param: Optional[LLMGenParams] = None

    def model_post_init(self, context):
        if self.llm_config:
            print("Start initializing LLM for `MessageContextEngine`.")
            self.llm = LLM(
                base_url=self.llm_config.base_url,
                api_key=self.llm_config.api_key,
                model=self.llm_config.model
            )
            print(f"MessageContextEngine llm has been initialized successfully!")
        
        if self.llm_gen_param is None:
            self.llm_gen_param = LLMGenParams(stream=False, temperature=0.8)
    
    def append(self, conversation_uuid:UUID, message:Message):
        """ append a new message for conversation uuid 
        
        Args:
            conversation_uuid(UUID): conversation uuid. A whole rounds have a unique conversation uuid.
            message(Message): new message
        """

        if conversation_uuid not in self.context.keys():
            print(f"{conversation_uuid} is not in MessageContextEngine. MessageContextEngine is creating a record for {conversation_uuid}.")
            self.context[conversation_uuid] = []
        self.context[conversation_uuid].append(message)

    def extract(self, query:str, conversation_uuid:UUID) -> ExtractResult:
        """ Extract relative content to query in conversation

        Args:
            query(str): query
            conversation_uuid(UUID): history conversation uuid. Should pass an existing in self.context uuid

        Returns:
            ExtractResult: extraction result

        Raises:
            ValueError: conversation_uuid cannot be found in self.context. It's a new conversation uuid.
            ParseError: llm output a wrong format that cannot be parsed correctly.
        """

        if self.context.get(conversation_uuid, None) is None:
            raise ValueError(f"Fail to extract related something to `{query}`. Please check your passing conversation_uuid has been created.")

        conversations:List[Message] = self.context[conversation_uuid]
        history_messages = []
        # only consider user and assistant content
        for conversation in conversations:
            if conversation.role == "user":
                history_messages.append(f"user: {conversation.content}")
            elif conversation.role == "assistant":
                history_messages.append(f"assistant: {conversation.content}")
        history_messages = "\n".join(history_messages)

        sys_prompt_str = extract_prompt.format(
            START_EXTRACTION_TAG=START_EXTRACTION_TAG,
            NO_RELATED_EXTRACTION_TAG=NO_RELATED_EXTRACTION_TAG,
            user_query=query,
            history_messages=history_messages
        )
        sys_prompt = Message.system_message(sys_prompt_str)
        response:str = self.llm.generate_sync(prompts=[sys_prompt], params=self.llm_gen_param)
        if response.find(START_EXTRACTION_TAG):
            # plus one reason is a colon. It will return a START_EXTRACTION_TAG: (what extractions are)
            start_idx = response.find(START_EXTRACTION_TAG) + len(START_EXTRACTION_TAG) + 1
            return ExtractResult(relative=True, message=response[start_idx:])
        
        elif response.find(NO_RELATED_EXTRACTION_TAG):
            # plus one reason is a colon. It will return a NO_RELATED_EXTRACTION_TAG: (what extractions are)
            start_idx = response.find(NO_RELATED_EXTRACTION_TAG) + len(NO_RELATED_EXTRACTION_TAG) + 1
            return ExtractResult(relative=False, message=response[start_idx:])

        raise ParseError(f"Failed to parse extraction by MessageContextEngine: cannot find {START_EXTRACTION_TAG} and {NO_RELATED_EXTRACTION_TAG}.")

    def compress(self):
        ...

    @property
    def context_for_llm(self, conversation_uuid:UUID) -> list[dict]:
        """ context for llm directly not transform again """

        if conversation_uuid not in self.context.keys():
            return []
        conversation_ctx = self.context[conversation_uuid]
        llm_ctx:list[dict] = [ctx.model_dump(exclude_none=True) for ctx in conversation_ctx]
        return llm_ctx

    @property
    def context(self, conversation_uuid:UUID) -> list[Message]:
        """ message context """

        if conversation_uuid not in self.context.keys():
            return []
        return self.context[conversation_uuid]