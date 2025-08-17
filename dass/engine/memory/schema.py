from uuid import UUID
from uuid import uuid4
from datetime import datetime
from typing import Optional, Literal, List
from pydantic import BaseModel

from ... import qdrant
from ...qdrant import Filter, Record

class MemoryPayload(BaseModel):
    """ Memory payload 
    more information to describe the memory

    Args:
        created_time(datetime): when happens
        topic(str): the memory subject
        emotion(str): my emotion in the memory
        intention(Optional[str]): the intention when I talk about `Dass`
        weather(Literal): weather at created_time
    """
    
    created_time: datetime
    topic: str
    emotion: str
    intention: Optional[str]
    weather: Literal["sunny", "cloudy", "windy", "snowy", "raining-lightly", "raining-heavily"]

class Memory(BaseModel):
    """ Memory for later interaction

    Args:
        readable_mem(str): original memory but human readable
        embeddings(list[float]): embeddings of readable_mem
        payload(MemoryPayload): more information about readable_mem
        domain(Literal["work", "study", "technology", "relationship", "philosophy", "entertainment", "secrets"]): Memory big picture. It corresponds to `Qdrant` collections.
    """

    readable_mem: str
    embeddings: list[float]
    payload: MemoryPayload
    domain: Literal["work", "study", "technology", "relationship", "philosophy", "entertainment", "secrets"]

    def to_record(self) -> Record:
        """ Get record based on memory
        Record is interface data in interacting with Qdrant

        Returns:
            Record: record based on memory
        """

        id = uuid4()
        return Record(id=id, vector=self.embeddings, payload=self.payload, src=self.readable_mem)
    
    @staticmethod
    def convert_to_memory(scored_point:qdrant.ScoredPoint, collection_name:str) -> "Memory":
        """ covert a scored point to a memory
        Make sure scored point payload contains parameters of `MemoryPayload`.
        
        Args:
            scored_point(qdrant.ScoredPoint): scored point
            collection_name(str): collection name which scored_point is selected in.
        
        Returns:
            Memory: memory
        """
        
        src = scored_point.payload.get("src", "NO ANY HUNMAN READABLE CONTENT!PLEASE IGNORE IT!")
        vector:List[float] = scored_point.vector
        payload:MemoryPayload = MemoryPayload(
            created_time=scored_point.payload.get("created_time", datetime.now()),
            topic=scored_point.payload.get("topic", "NO TOPIC"),
            emotion=scored_point.payload.get("emotion", "NO EMOTION WHEN CHATTED AT THE TIME."),
            intention=scored_point.payload.get("intention", "NO INTENTION WHEN CHATTED AT THE TIME."),
            weather=scored_point.payload.get("weather", "UNKNOW WEATHER WHEN CHATTED AT THE TIME.")
        )
        return Memory(readable_mem=src, embeddings=vector, domain=collection_name, payload=payload)

class MemorySearchRequest(BaseModel):
    """ one memory search request
    Every request can search top_k relative memories of query in one or more than one collections by the same filter now. In the later multi-filters will be supported.
    Notice not pass collections means search in all existing collections.
    
    Args:
        id(UUID): query uuid. Created automatically.
        query(str): query
        collections(Optional[str | list[str]]): collections searching in. Default to `None`. 
                                                If `None` means search in all existing collections.
        limit_in_one_collection(int): limit number searching in one collection. Default to 8. It doesn't support a list to make different limit in different collections. Probably introduce it in later version.
        top_k(int): top_k represents most relative number in search results from collections. Default to 8.
        with_payload(bool): whether return payload which includes `Memory.readable_mem`. Default to `True`.
        with_vector(bool): whether return vectors. Default to `False`.
        score_threshold(float): A minimal score threshold for the result. If defined, less similar results will not be returned. 
                                Score of the returned result might be higher or smaller than the threshold depending on the Distance function used. E.g. for cosine similarity only higher scores will be returned.
                                Default to `0.6`.
    """

    id: UUID = uuid4()
    query: str
    collections: Optional[str | list[str]] = None
    filter: Optional[Filter] = None
    limit_in_one_collection: int = 8
    top_k: int = 8
    with_payload: bool = True
    with_vector: bool = False
    score_threshold: float = 0.6

    def model_post_init(self, context):
        if self.collections is None:
            self.collections:List[str] = qdrant.exist_collections_name()

class CollectionSearchResult(BaseModel):
    """ search result in a collection
    
    Args:
        collection_name(str): in which collection_name
        limit_most_relative_memories(list[Memory]): the limit most relative memories in a collection
    """

    collection_name: str
    limit_most_relative_memories: list[Memory]

class MemorySearchResult(BaseModel):
    """ One search memeory results
    Due to search in one or more collections with one query, search results will include a (n_collections, limit_k) to clearly see which memories searched in collections
    and a top_k list which represents top_k most relative memory in results from n_collections.
    Also be capable to trace back to it belongs to which memory search request

    Args:
        id(UUID): result id. Created automatically.
        from_search_request_id(UUID): which request it belongs to.
        most_relative_memories(list[Memory]): top_k, in memory search request, most relative memories
        collections_search(list[CollectionSearchResult]): a list of searching the limit most relative memories in one collection
    """
    id: UUID = uuid4()
    from_search_request_id: UUID
    most_relative_memories: list[Memory]
    collections_search: list[CollectionSearchResult]