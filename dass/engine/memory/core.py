from typing import Optional, List, Dict
from pydantic import BaseModel
from openai import OpenAI
from openai.types.embedding import Embedding as EmbedResult

from ...config.load import EmbeddingConfig
import qdrant
from .schema import Memory, MemorySearchRequest, MemorySearchResult, CollectionSearchResult

class Embedding(BaseModel):
    provider: str
    base_url: str
    api_key: str
    model: str
    _cli: Optional[OpenAI] = None

    def __post_init__(self):
        self._cli = OpenAI(base_url=self.base_url, api_key=self.api_key)

    def __call__(self, query:str | list[str], dim:int) -> List[List[float]]:
        """ embedding

        Args:
            query(str | list[str]): query can be one or a batch
            dim(int): embedding dimensions which is decided generally by `MemoryEngine`
        
        Returns:
            List[List[float]]: (query_number, embeddings)
        """
        response = self._cli.embeddings.create(
            input=query,
            model=self.model,
            dimensions=dim
        )
        data:List[EmbedResult] = response.data
        embeddings:List[List[float]] = [embed.embedding for embed in data]
        return embeddings

class MemoryEngine(BaseModel):
    """ Memory engine
    Memory engine is the unique way to interact with `qdrant` now. It's an abstraction layer above the qdrant to make store, delete, search memeory easier.
    It only supports text memory now. Hope importing images, audios, and vedios.
    
    Args:
        dim(int): embedding dimensions. Generally be decided by QDrantConfig
        config(EmbeddingConfig): embedding config
        embedding(Optional[Embedding]): to embed memory
    """

    dim: int = 1024
    config: EmbeddingConfig
    embedding: Optional[Embedding] = None
    
    def model_post_init(self, context):
        self.embedding = Embedding(
            provider=self.config.provider,
            base_url=self.config.base_url,
            api_key=self.config.api_key,
            model=self.config.model
        )
    
    def _embedding(self, text:str | list[str]) -> List[List[float]]:
        """ embed string or a list of string to vector 
        
        Args:
            text(str | list[str]): text to be embedded
        
        Returns:
            List[List[float]]: (query_number, embeddings)
        """

        return self.embedding(query=text, dim=self.dim)

    def _transfer_to_qdrant_search_request(self, memory_search_request:MemorySearchRequest) -> qdrant.SearchRequest:
        """ transfer a MemorySearchRequest to Qdrant search request 
        
        Args:
            memory_search_request(MemorySearchRequest): memory search request
        
        Returns:
            qdrant.SearchRequest: a qdrant official search request
        """
        
        vector:List[float] = self._embedding(memory_search_request.query)[0]
        return qdrant.SearchRequest(
            vector=vector,
            filter=memory_search_request.filter,
            limit=memory_search_request.limit_in_one_collection,
            score_threshold=memory_search_request.score_threshold,
            with_payload=memory_search_request.with_payload,
            with_vector=memory_search_request.with_vector
        )

    def store(self, memory:list[Memory] | Memory) -> List[qdrant.UpdateResult]:
        """ store one or more Memory 
        upsert one by one. Need more effection and safety methods.

        Args:
            memory(list[Memory] | Memory): memory to be stored

        Returns:
            List[qdrant.UpdateResult]: update result of these memories.
        """

        if isinstance(memory, Memory):
            memory = [memory]

        update_results = []
        for mem in memory:
            collection_name = memory.domain
            record = memory.to_record()
            update_result:qdrant.UpdateResult = qdrant.upsert(collection_name=collection_name, records=record)
            update_results.append(update_result)
        return update_results

    def search(self, search_requests:list[MemorySearchRequest] | MemorySearchRequest) -> list[MemorySearchResult] | MemorySearchResult:
        """ search memory
        One request corresponds one result! It supports search only one by one now. 
        However if can parse the search_requests and compose a batch search based on the same target collections, then use qdrant.search(collection_name, queries) which will return a list of every query memory in the collections. It's very effective.
        After returns the list of every query we have to manages the result composation. There are many conditions need to be considered. Hopefully support it in the later version.

        Notice: it's probable that `MemorySearchResult.most_relative_memories` and `MemorySearchResult.collections_search` are empty because there is no relative content with request query.

        Args:
            search_request(list[MemorySearchRequest] | MemorySearchRequest): one or more than one search request.
        
        Returns:
            list[MemorySearchResult] | MemorySearchResult: return MemorySearchResult if search_requests type is not list. Otherwise return a list.
        """

        if isinstance(search_requests, MemorySearchRequest):
            search_requests = [search_requests]
        
        # (k_requests, top_k_points)
        final_results:List[MemorySearchResult] = []
        for request in search_requests:
            # probably all_results length is 0 because no vectors are matched.
            # Dict includes two keys: collection_name and scored_point
            all_results:List[Dict[str, str | qdrant.ScoredPoint]] = []
            collections_search_result:List[CollectionSearchResult] = []
            top_k = request.top_k
            qdrant_request:qdrant.SearchRequest = self._transfer_to_qdrant_search_request(memory_search_request=request)
            collection_names:List[str] = request.collections if isinstance(request.collections, list) else [request.collections]

            for collection_name in collection_names:
                # get limit number of scored points with calling qdrant.search passing one request
                matched_points:List[qdrant.ScoredPoint] = qdrant.search(collection_name=collection_name, requests=qdrant_request)[0]
                for point in matched_points:
                    all_results.append({
                        "collection_name": collection_name,
                        "scored_point": point
                    })
                matched_memories:List[Memory] = [Memory.convert_to_memory(scored_point=point, collection_name=collection_name) for point in matched_points]
                collections_search_result.append(CollectionSearchResult(collection_name=collection_name, limit_most_relative_memories=matched_memories))

            # select top_k most relative in all collections query results
            top_k_most_relative_items:List[Dict[str, str | qdrant.ScoredPoint]] = sorted(all_results, key=lambda x: x["scored_point"].score, reverse=True)[:top_k]
            top_k_memories = [
                Memory.convert_to_memory(scored_point=item['scored_point'], collection_name=item['collection_name']) 
                for item in top_k_most_relative_items
            ]
            memory_search_reuslt = MemorySearchResult(from_search_request_id=request.id, most_relative_memories=top_k_memories, collections_search=collections_search_result)
            final_results.append(memory_search_reuslt)
        
        return final_results if len(final_results) != 1 else final_results[0]