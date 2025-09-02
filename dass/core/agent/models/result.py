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
        actions(Optional[list[Action]]): actions that super agent will take
        done(bool): whether subplan can be terminate.
        final_answer(Optional[str]): final answer for subplan. Default to None
    """

    selection: Optional[Literal["make_todo_list", "analyze", "fix", "solved", "obscure"]] = None
    subplan: Optional[SubPlan] = None
    actions: list[Action]
    done: bool
    final_answer: Optional[str] = None

class ParsedThinkResult(BaseModel):
    """ Think result after parsing the think repsonse of super agent
    
    Args:
        selection(Literal["make_todo_list", "analyze", "fix", "solved", "obscure"]): selection of super agent. You can see the prompt of these five string at ../../prompts/__init__.py
        selected_todo_item(Optional[str]): which one todo item that super agent choose to analyze. Only set when selection equals to `analyze`. Default to None. 
        done(bool): whether info is final answer
        info(str|TODOList): think response concrete information.

    Raises:
        ValueError: selected_todo_item is set when selection is not `analyze`. 
    """

    selection: Literal["make_todo_list", "analyze", "fix", "solved", "obscure"]
    selected_todo_item: Optional[str] = None
    done: bool
    info: str | TODOList

    def model_post_init(self, context):
        if self.selection != "analyze" and self.selected_todo_item:
            raise ValueError("Expected to `ParsedThinkResult` has selected_todo_item only when selection equals to `analyze`.")
        
class ExecutionResult(BaseModel):
    """ Super agent execute one react loop result

    Args:
        done(bool): whether terminate
        final_answer(Optional[str]): final answer if done is True. Default to None.
    """

    done:bool
    final_answer:Optional[str] = None