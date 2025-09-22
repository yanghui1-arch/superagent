from typing import Optional, Literal
from pydantic import BaseModel
from .react.plan import SubPlan, TODOList
from . import Action 

class ThinkResult(BaseModel):
    """ Super agent think result
    ThinkResult includes which one selection super agent choose, whether the subplan is terminated and other is Optional variable.

    Args:
        selection(Literal["make_todo_list", "analyze", "fix", "solved", "obscure"]): which one selction super agent choose.
        subplan(Optional[SubPlan]): subplan.  
        actions(Optional[list[Action]]): actions that super agent will take. Default to None.
        done(bool): whether subplan can be terminate.
        final_answer(Optional[str]): final answer for subplan. Default to None
    """

    selection: Optional[Literal['solved', 'obscure', 'call_tool']] = None
    actions: list[Action]|None = None
    done: bool
    final_answer: Optional[str] = None
        
class ExecutionResult(BaseModel):
    """ Super agent execute one react loop result

    Args:
        done(bool): whether terminate
        final_answer(Optional[str]): final answer if done is True. Default to None.
    """

    done:bool
    final_answer:Optional[str] = None