from typing import Optional, ClassVar
from pydantic import BaseModel
from pydantic import Field
from .todo import TODOList, TODOItem
from .....prompts import NO_COMPLETED_TAG, COMPLETED_TAG

class Plan(BaseModel):
    """ Plan is a complete solution for a user question in a whole.
    user_question -> a planlist -> decompose lots of todo lists -> solve items one by one -> back to todo lists -> summarize the observations -> judge whether solve the user question
    Super agent will decompose a big plan to some smaller sub-plans and then make a todo list for these plans.


    Args:
        overall_goal(str): final target. all following arguments are generated based on target
        subplans(list[SubPlan]): a list of detailed subplans. Default to `[]`.
        steps(dict[str, bool]): smaller steps to achive overall goal. Key is the subplans description. Value is whether completed
        completed(bool): whether plan is completed. Default to False.
    """

    COMPLETED_TAG:ClassVar[str] = COMPLETED_TAG
    NO_COMPLETED_TAG:ClassVar[str] = NO_COMPLETED_TAG

    overall_goal: str
    steps: dict[str, bool]
    subplans:list["SubPlan"] = Field(default_factory=list, init=False)
    completed: bool = False

    @property
    def subplans_desc(self) -> list[str]:
        return [sub_plan for sub_plan, _ in self.steps.items()]
    
    @property
    def subplans_detailed(self) -> list["SubPlan"]:
        return self.subplans
    
    @property
    def steps_detailed(self) -> str:
        detailed_info = ""
        for subplan, complete in self.steps.items():
            detailed_info += f"{Plan.COMPLETED_TAG if complete else Plan.NO_COMPLETED_TAG} {subplan} \n"
        return detailed_info

class SubPlan(BaseModel):
    """ sub plan class
    Super agent will make a plan, including lots of subplans, for a question. Super agent doesn't make any todo list during this time. So Plan.steps only includes a subplan description.
    `SubPlan` class emerges at this time. It solves how super agent can do to achive the subplan

    Args:
        detailed_info(str): detailed information about the subplan.
        todo_list(Optional[TODOList]): todo list to achive subplan. Default to None.
        completed(bool): whether subplan is completed. Default to `False`.
    """

    detailed_info: str
    todo_list: Optional[TODOList] = None
    completed: bool = False

    def __repr__(self):
        todo_list:list[str] = []
        if self.todo_list:
            for idx, todo_item in enumerate(self.todo_list.todo_items()):
                todo_list.append(f" {idx}. {todo_item}")
        return f"Subplan: {self.detailed_info}\nTODO List:\n{"\n".join(todo_list)}"


__all__ = [
    "Plan",
    "SubPlan",
    "TODOList",
    "TODOItem"
]