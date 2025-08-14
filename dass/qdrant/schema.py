from uuid import UUID
from typing import Optional
from pydantic import BaseModel
from qdrant_client.models import PointStruct, Match, RangeInterface, ValuesCount
from qdrant_client.models import Filter as QdrantFilter
from qdrant_client.models import MinShould as QdrantMinShould

class Condition(BaseModel):
    """ Condition for read or delete
    You can consider `condition` is `where` clause in SQL.
    One condition should include just one condition which means only one of `match`, `range`, `values_count`, `is_empty`, and `is_null` exists in `Condition` class instance.

    Args:
        key(str): field name you want to select
        match(Optional[Match]): match conditions. Default to None.
                                `MatchValue(value=2)` means key's value should match value 2
                                `MatchText(text="You they") means select strings in key's value has `you` or `they` and no matter their order. Generally used in `list[str]` or `str`
                                `MatchPhrase(phrase="fast cat")` means select strings in key's value has `fast car` and make sure these two words are near in the location.
                                others please check qdrant Match docs manually.
        range(Optional[RangeInterface]): a range of value or date. Default to None.
                                        `Range`: used on number value. Has `gt(greater than), gte(greater than equal), lt(less than), lte(less than equal)`
                                        `DatetimeRange`: used on date. Args as the same as above.
        values_count(Optional[ValuesCount]): select the key's values number should be gt/gte/lt/lte a value. For example you want to select comment that number is greater than 3 and you should use values_count but not range. Because `range` is range `value` and `values_count` is count `value's number`.
        is_empty(Optional[bool]): is empty. Default to None.
        is_null(Optional[bool]): is null. Default to None.
    """
    
    key: str
    match: Optional[Match] = None
    range: Optional[RangeInterface] = None
    values_count: Optional[ValuesCount] = None
    is_empty: Optional[bool] = None
    is_null: Optional[bool] = None

class AtLeastMatchNConditions(BaseModel):
    """ At least n conditions should be matched
    
    Args:
        n(int): number of should be matched conditions
        conditions(list[Condition]): a series of condition candidates.
    """
    n: int
    conditions: list[Condition]

class Filter(BaseModel):
    """ Compose all conditions in a filter
    Although qdrant_client.models have `Filter` class it's not clear to use in the project and so have to reclaim a new `Filter` class to be enough clear for dass project.
    Only select one of `must`, `must_not`, `at_least_one`, `at_least_n`
    
    Args:
        must(Optional[Condition | list[Condition]]): must match these conditions
        must_not(Optional[Condition | list[Condition]]): must not match these conditions
        at_least_match_one(Optional[Condition | list[Condition]]): at least match one conditions of them
        at_least_match_n(Optional[AtLeastMatchNConditions]): at least match n conditions of them
    """
    
    must: Optional[Condition | list[Condition]] = None
    must_not: Optional[Condition | list[Condition]] = None
    at_least_match_one: Optional[Condition | list[Condition]] = None
    at_least_match_n: Optional[AtLeastMatchNConditions] = None

    def model_post_init(self, context):
        """ validate only one model included in filter """
        not_none_attr_nums = sum([1 for attr in [self.must, self.must_not, self.at_least_match_one, self.at_least_match_n] if attr is not None])
        if not_none_attr_nums == 0:
            raise ValueError("Filter should include only one of `must`, `must_not`, `at_least_match_one` and `at_least_match_n`. Please re-check your zero attributes passed `Filter` initialization.")
        if not_none_attr_nums > 1:
            raise ValueError("Filter should include only one of `must`, `must_not`, `at_least_match_one` and `at_least_match_n`. Please re-check your exceed one attributes passed `Filter` initialization.")

    def to_qdrant_filter(self) -> QdrantFilter:
        """ transform project's filter to qdrant official filter """

        if self.must:
            return QdrantFilter(must=self.must)
        if self.must_not:
            return QdrantFilter(must_not=self.must_not)
        if self.at_least_match_one:
            return QdrantFilter(should=self.at_least_match_one)
        if self.at_least_match_n:
            min_should = QdrantMinShould(min_count=self.at_least_match_n.n, conditions=self.at_least_match_n.conditions)
            return QdrantFilter(min_should=min_should)

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