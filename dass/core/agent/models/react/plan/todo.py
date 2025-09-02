from typing import ClassVar, Literal
from pydantic import BaseModel

from .....prompts import NO_COMPLETED_TAG, COMPLETED_TAG

class TODOItem(BaseModel):
    """ todo item 
    
    Args:
        order(int): item order. Higher -> Later, Lower -> Earlier. Same -> Meanwhile executing.
        content(str): item concrete content.
        status(Literal["completed", "no-completed"]): item current status. Default to `no-completed`
    """
    
    no_completed_tag: ClassVar[str] = NO_COMPLETED_TAG
    completed_tag: ClassVar[str] = COMPLETED_TAG

    order: int
    content: str
    status: Literal["completed", "no-completed"] = "no-completed"

    def __repr__(self):
        return f"{TODOItem.no_completed_tag if self.status=="no-completed" else TODOItem.completed_tag} {self.content}"

    def mark_complete(self) -> bool:
        """ to sign the item completed
        Replace `- []` to `- [x]`

        Returns:
            bool: whether complete successfully.
        """

        if self.status == "completed":
            print(f"[WARNING]: todo item `{self.content}` has been completed before.")
        self.status = "completed"
        self.content = self.content.replace(TODOItem.no_completed_tag, TODOItem.completed_tag, 1)
        return True

class TODOList(BaseModel):
    """ todo list
    Agent create a todo list and complete every item step by step. Some items can be executed at the same time if TODOItem orders are the same.

    Args:
        plan_list(list[TODOItem]): a todo list
        completed(bool): whether todo list has been solved. Default to False.
    """

    plan_list: list[TODOItem]
    completed: bool = False
    
    def __repr__(self):
        return "TODO List:\n" + "\n".join(self.plan_list)

    def complete_todo_item(self, todo_item_idx:int) -> "TODOList":
        """ update todo item status and completed, no-completed counts

        Args:
            todo_item_idx(int): index of todo item. NOT order!! MUST be idx!!

        Returns:
            TODOList: self todo list
        """

        if todo_item_idx >= len(self.plan_list) or todo_item_idx < 0:
            raise ValueError(f"todo_item_idx cannot be {todo_item_idx}. Please ensure its range is in [0, {len(self.plan_list)})")
        
        todo_item = self.plan_list[todo_item_idx]
        completed = todo_item.mark_complete()
        if completed:
            self.completed_cnt += 1
            self.no_completed_cnt -= 1

        if self.no_completed_cnt < 0:
            print(f"[WARNING]: no-completed count is below 0 when complete plan.")
        return self

    @property
    def todo_items(self) -> list[TODOItem]:
        return self.plan_list