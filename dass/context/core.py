from abc import ABC
from abc import abstractmethod
from datetime import datetime
from typing import List, Dict

from pydantic import BaseModel
from uuid import UUID
from dass.engine.message import Message

# Message or Memory
Context = Message

class ContextEngine(BaseModel, ABC):
    """ ContextEngine manages conversations with llm. """
    start_time: datetime

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


class MessageContextEngine(ContextEngine):
    """ Message context engine focus on management about message.
    Its main task is to record active round conversation with llm and store the messages with various strategies.

    Args:
        context(Dict[UUID, List[Message]]): record all messages for every conversation.
    """

    def __init__(self):
        super().__init__()
        self.context:Dict[UUID, List[Message]] = {}
    
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

    def extract(self):
        ...

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