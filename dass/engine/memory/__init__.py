""" memory standard interface

MemoryEngine is most important for Dass because it makes Dass retrieve anything valuable in any time and use them to take an action.
Focus on search memory, delete outdated memories and upsert new memories. MemoryEngine has interactions with Qdrant vector database now and will support more vector database/ graph database such as faiss and neo4j in the future.
No matter where memory is stored if want to search memory just pass one MemorySearchRequest or a list of MemorySearchRequest and response one MemorySearchResult or a list of MemorySearchResult.
"""

from .constants import (
    my_emotions, 
    relationship_sub_topics,
    study_sub_topics,
    technology_sub_topics,
    work_sub_topics,
    philosophy_sub_topics,
    entertainment_sub_topics,
    secrets_sub_topics
)

from .core import MemoryEngine
from .schema import Memory, MemoryPayload, MemorySearchRequest, MemorySearchResult, CollectionSearchResult

__all__ = [
    "MemoryEngine",
    "Memory",
    "MemoryPayload",
    "MemorySearchRequest",
    "MemorySearchResult",
    "CollectionSearchResult",
    "my_emotions",
    "relationship_sub_topics",
    "study_sub_topics",
    "technology_sub_topics",
    "work_sub_topics",
    "philosophy_sub_topics",
    "entertainment_sub_topics",
    "secrets_sub_topics"
]