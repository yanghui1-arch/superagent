from uuid import UUID
from .core import MessageContextEngine
from ..message import Message

__all__ = ["MessageContextEngine", "init"]

_message_context_engine = None

def init():
    global _message_context_engine
    _message_context_engine = MessageContextEngine()

def message_append(conversation_uuid:UUID, message:Message):
    global _message_context_engine
    if not _message_context_engine:
        raise SystemError("Please initialize MessageContextEngine when you try to use context.some_functions().")
    
    _message_context_engine.append(conversation_uuid=conversation_uuid, message=message)