from uuid import UUID
from typing import Optional
from pydantic import BaseModel
from qdrant_client.models import PointStruct

class Condition(BaseModel):
    """ Condition for read or delete
    You can consider `condition` is `where` clause in SQL.

    Args:
        key(str): payload key
        value(str): value of key 
    """
    
    field_key: str
    field_value: int | str | dict

class Record(BaseModel):
    """ Record rules that every PointStruct has a source content named `src`
    Every point to be stored in qdrant should has its own human-readable content and Record class specified src as original content.

    Args:
        id(UUID): PointStruct id
        vector(list[float]): embedded vector of src
        payload(dict): more information about src. Default to `None`.
        src(str): source content.
    """
    id: UUID
    vector: list[float]
    payload: Optional[dict] = None
    src: str

    def to_point(self):
        """ Get the point given the record instance
        
        Returns:
            PointStruct: standard point in dqrant based on the Record instance caller.
        """
        payload = {}
        payload['src'] = self.src
        if self.payload:
            for k, v in self.payload.items():
                payload[k] = v
        return PointStruct(id=self.id, vector=self.vector, payload=payload)
    
    @staticmethod
    def from_point_to_record(point:PointStruct):
        """ Transform a point to a record 
        Make sure point has payload and payload includes `src` key.

        Raises:
            ValueError: if point doesn't have payload or payload doesn't have `src`.
        """
        if not point.payload:
            raise ValueError(f"point {point} has no payload. Please make sure point has payload.")
        
        src = point.payload.get("src", None)
        if src is None:
            raise ValueError(f"point {point} src is None. Please check code logic about upsert of qdrant.")
        payload = point.payload
        payload.pop("src")

        return Record(id=UUID(point.id), vector=point.vector, payload=payload, src=src)