from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance
from qdrant_client.models import PointStruct
from qdrant_client.models import UpdateResult
from qdrant_client.models import Filter, FieldCondition, MatchValue
from qdrant_client.models import SearchRequest, ScoredPoint

from .schema import Condition
from dass.config.load import QDrantConfig


class QdrantManager(BaseModel):
    """ QdrantManager manages upsert, delete, search opertions about qdrant vector database.
    QdrantManager is created by passing a QDrantConfig. Not implement it as a singleton as I want make more managers manages qdrant effectively in the multi-process env later.
    
    Args:
        config(QDrantConfig): qdrant config
        _vectors_config(Optional[VectorParams]): qdrant vector dim and distance config. Default to `None`.
        _client(Optional[QdrantClient]): qdrant client. Default to `None`
        _search_counts(int): search counts. No matter one batch search or one request search are both one search.
        _upsert_counts(int): upsert counts.
    """

    config: QDrantConfig
    _vectors_config: Optional[VectorParams] = None
    _client: Optional[QdrantClient] = None
    _search_counts: int = 0
    _upsert_counts: int = 0

    _collections = [
        "work",
        "study",
        "technology",
        "relationship"
        "philosophy",
        "entertainment",
        "secrets"
    ]

    _distance_type_mapping = {
        "cosine": Distance.COSINE,
        "euclid": Distance.EUCLID,
        "dot": Distance.DOT,
        "manhattan": Distance.MANHATTAN
    }

    def __post_init__(self):
        """ Qdrant client init and create collections if not exists """

        if not self._client:
            print("Start init Qdrant ...")

            host = self.config.host
            port = self.config.port
            dim  = self.config.dim
            distance = self._distance_type_mapping[self.config.distance_type]
            
            self._client = QdrantClient(host=host, port=port)
            self._vectors_config = VectorParams(size=dim, distance=distance)
            
            for collection in self._collections:
                if not self._client.collection_exists(collection_name=collection):
                    self._client.create_collection(
                        collection_name=collection,
                        vectors_config=self._vectors_config
                    )
                    print(f"Cannot find the {collection} in Qdrant. {collection} collection is created with {dim} vector dimensions and search strategy is {distance.value} at {datetime.now()}.")

            print(f"Qdrant is initialized successfully.")

    def upsert(self, collection_name:str, points:list[PointStruct]) -> UpdateResult:
        self._upsert_counts += 1
        return self._client.upsert(collection_name=collection_name, points=points)
    
    def delete_points(
        self,
        collection_name:str,
        to_delete_points_ids:Optional[list[str] | str]=None,
        conditions:Optional[list[Condition] | Condition]=None
    ) -> UpdateResult:
        """ delete points by id or select conditions
        Pass only one parameter of to_delete_points_id and conditions. If pass to_delete_points_id qdrant will delete by ids. On the contrary pass conditions qdrant will delete by conditions.

        Args:
            to_delete_points_id(Optional[list[str] | str]): points ids to delete. `str` type means just one. Default to None
            conditions(Optional[list[Condition]]): delete points which satisfied all conditions. Default to None
        
        Returns:
            UpdateResult: qdrant update result
        
        Raises:
            ValueError: 1. Not pass to_delete_points_ids or conditions.
                        2. Pass to_delete_points_ids and conditions together.
                        3. Pass a not existing collection name
        """

        if (not to_delete_points_ids and not conditions) or (to_delete_points_ids and conditions):
            raise ValueError("Please make one but only one of `to_delete_points_id` and `conditions` id exist. Don't pass two or none.")
        
        if not self._client.collection_exists(collection_name=collection_name):
            raise ValueError(f"Doesn't find {collection_name} collection in your qdrant. Please pass an existing collection name.")

        if to_delete_points_ids:
            if isinstance(to_delete_points_ids, str):
                to_delete_points_ids = [to_delete_points_ids]
            return self._client.delete(collection_name=collection_name, points_selector=to_delete_points_ids)
        
        field_must_conditions:List[FieldCondition] = []
        if isinstance(conditions, Condition):
            conditions = [conditions]
        for condition in conditions:
            key = condition.field_key
            value = condition.field_value
            match_value = MatchValue(value=value)
            field_must_conditions.append(FieldCondition(key=key, match=match_value))
        draft_filter:Filter = Filter(must=field_must_conditions)
        return self._client.delete(collection_name=collection_name, points_selector=draft_filter)

    def search(
        self,
        collection_name:str,
        requests: list[SearchRequest] | SearchRequest
    ) -> list[list[ScoredPoint]]:
        """ search relevant points batched 
        Return explaination -> (k_requests, top_p_relevant_points). top_p_relevant is decided by different request so the second dim is not the same.

        Args:
            collection_name(str): search in collection_name
            requests(list[SearchRequest] | SearchRequest): one or more request
        
        Returns:
            list[list[ScoredPoint]]: `top_p` relative points corresponds to every request.
        """

        if not self._client.collection_exists(collection_name=collection_name):
            raise ValueError(f"Doesn't find {collection_name} collection in your qdrant. Please pass an existing collection name.")
        
        if isinstance(requests, SearchRequest):
            requests = [requests]
        self._search_counts += 1
        return self._client.search_batch(collection_name=collection_name, requests=requests)

    @property
    def exists_collections(self):
        return self._collections
    
    @property
    def distance_type_mapping(self):
        return self._distance_type_mapping
    
    @property
    def search_counts(self):
        return self._search_counts
    
    @property
    def upsert_counts(self):
        return self._upsert_counts