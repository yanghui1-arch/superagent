from uuid import UUID
from typing import Optional, List

from qdrant_client.models import PointStruct, UpdateResult, SearchRequest, ScoredPoint

from .cli import QdrantManager
from .schema import Condition, Record
from ..config.load import QDrantConfig

__all__ = [
    "QdrantManager",
    "Condition",
    "Record",
    "init",
    "upsert",
    "delete",
    "search"
]

_manager:Optional[QdrantManager] = None

def init(config:QDrantConfig):
    global _manager
    _manager = QdrantManager(config=config)

def upsert(collection_name:str, records:Record | list[Record]) -> UpdateResult:
    """ insert and update points in collection 
    
    Args:
        collection_name(str): collection name to upsert
        records:(Record | list[Record]): records to be upserted in collection

    Raises:
        SystemError: call it but not init _manager
    """

    global _manager
    if not _manager:
        raise SystemError("Please call qdrant.init() first before calling qdrant.upsert().")
    
    if isinstance(records, Record):
        records = [records]
    points:List[PointStruct] = [record.to_point() for record in records]
    return _manager.upsert(collection_name=collection_name, points=points)

def delete_points(collection_name:str, to_delete_points_ids:Optional[list[UUID] | UUID]=None, conditions:Optional[list[Condition] | Condition]=None) -> UpdateResult:
    """ Delete points by ids or conditions.
    Pass `to_delete_points_ids` -> delete these ids points. Pass `conditions` -> delete points which satisfy all these conditions.
    It's forbidden to pass them both together.

    Args:
        collection_name(str): collection to delete points
        to_delete_points_ids(Optional[list[UUID] | UUID]): points ids to delete. Default to None.
        conditions(Optional[list[Condition] | Condition]): conditions that caller want to delete satisying these conditions points
    
    Returns:
        UpdateResult: qdrant update result

    Raises:
            ValueError: 1. Not pass to_delete_points_ids or conditions.
                        2. Pass to_delete_points_ids and conditions together.
                        3. Pass a not existing collection name
            SystemError: call it but not init _manager
    """

    global _manager
    if not _manager:
        raise SystemError("Please call qdrant.init() first before calling qdrant.delete().")
    return _manager.delete_points(collection_name=collection_name, to_delete_points_ids=to_delete_points_ids, conditions=conditions)

def search(collection_name:str, requests:list[SearchRequest] | SearchRequest) -> List[List[ScoredPoint]]:
    """ qdrant search
    Support batch search.

    Args:
        collection_name(str): collection to be searched
        requests(list[SearchRequest] | SearchRequest): search requests
    
    Returns:
        List[List[ScoredPoint]]: related points. -> (k_requests, limit_related_points_every_request)
    
    Raises:
        SystemError: call it but not init _manager
    """
    global _manager
    if not _manager:
        raise SystemError("Please call qdrant.init() first before calling qdrant.search().")
    
    for request in requests:
        if request.with_payload is None:
            request.with_payload = True
        if request.score_threshold is None:
            request.score_threshold = 0.6

    return _manager.search(collection_name=collection_name, requests=requests)