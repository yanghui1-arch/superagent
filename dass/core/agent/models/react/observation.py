from abc import ABC, abstractmethod
from typing import Optional
from .plan import Plan, SubPlan, TODOList, TODOItem

class Observable(ABC):
    @property
    @abstractmethod
    def obs(self):
        ...

class Observation(Observable):
    """Observation includes all details about plan.
    Super agent observations boil down to a few options.
    First subplan status, focusing on whether subplan has been solved and how to do it.
    Second todo list status. As designed before, there is a todo list in a subplan which is essential to achieve subplan. So super agent need todo list observations.
    Third todo item status. How to finish todo items one by one and finally achieve a todo list.
    Subplan status is not only todo list status but directly solve the subplan. Due to optional todo list, not every subplan has a todo list. The easy subplan will be solved directly by super agent with tools or just self capabilities.
    """

    def __init__(self, plan:Plan):
        self.plan_status = PlanStatus(plan=plan)
    
    @property
    def obs(self):
        return self.plan_status.obs

class PlanStatus(Observable):
    """ plan status
    
    Args:
        plan(Plan): plan
        subplan_status_list(list[SubPlanStatus]): all subplans status of the plan
        solution(Optional[str]): plan solution. Default to None
    """

    def __init__(self, plan:Plan):
        self.plan = plan
        self.subplan_status_list:list["SubplanStatus"] = [SubplanStatus(subplan=subplan) for subplan in self.plan.subplans]
        self.solution:Optional[str] = None

    def solved(self) -> bool:
        return self.solution or all([subplan_status.solved() for subplan_status in self.subplan_status_list])

    @property
    def obs(self):
        return f"""Plan: {self.plan}\tStatus:{"completed" if self.solved() else "no-completed"}
        {"\n".join([subplan_status.obs for subplan_status in self.subplan_status_list])}
        """

class SubplanStatus(Observable):
    """Subplan status
    To track subplan completed status. Not all subplans have a todo list. For easy subplan super agent can give solution directly.

    Args:
        subplan(Subplan): subplan to track
        solution(Optional[str]): subplan solution
        todo_list_status(Optional[TODOListStatus]): todo list status if subplan has todo list else None.
    """

    NOT_SOLVED = "It hasn't been solved yet."

    def __init__(self, subplan:SubPlan, solution:Optional[str]=None):
        self.subplan = subplan
        self.solution:Optional[str] = solution
        self.todo_list_status = None
        if subplan.todo_list:
            self.todo_list_status = TODOListStatus(todo_list=subplan.todo_list)

    def solved(self) -> bool:
        return not(self.solution is None and (self.todo_list_status is None or not self.todo_list_status.solved()))

    @property
    def obs(self) -> str:
        if not hasattr(self, "todo_list_status"):
            return self.solution if self.solution else SubplanStatus.NOT_SOLVED

        return f"""Subplan: {self.subplan.detailed_info}\tStatus: {"completed" if self.solved() else "no-completed"}
        {self.todo_list_status.obs}
        """
        
class TODOListStatus(Observable):
    """todo list status
    
    Args:
        todo_list(TODOList): todo list
        solution(Optional[str]): solution of todo list containing all todo items solutions. Default to None
        todo_items_status(list[TODOItemStatus]): todo items status.
    """

    NOT_SOLVED = "It hasn't been solved yet."

    def __init__(self, todo_list:TODOList):
        self.todo_list = todo_list
        self.solution:Optional[str] = None
        self.todo_items_status:list[TODOItemStatus] = [TODOItemStatus(todo_item=todo_item) for todo_item in todo_list.todo_items]

    def index(self, todo_item:TODOItem) -> "TODOItemStatus":
        """ index a todo item status
        
        Args:
            todo_item(TODOItem): todo item
        
        Returns:
            TODOItemStatus: indice todo item status
        """

        return next((todo_item_status for todo_item_status in self.todo_items_status if todo_item_status.todo_item.content == todo_item.content))
    
    def check_all_todo_items_solved(self) -> bool:
        """ check whether all todo items solved
        
        Returns:
            bool: return True if all todo items are solved
        """

        for todo_item_status in self.todo_items_status:
            if todo_item_status.solution == TODOItemStatus.NOT_SOLVED:
                print(f"[WARNING]TODOItem: `{todo_item_status.todo_item.content}` has not been solved. So the todo list should not call solved() function.")
                return False
        return True

    def solved(self) -> bool:
        """ todo list is solved while all todo items are solved
        

        Returns:
            bool: whether solved
        """

        all_todo_items_solved = self.check_all_todo_items_solved()
        
        if all_todo_items_solved:
            solution = "\n".join([todo_item_status.obs for todo_item_status in self.todo_items_status])
            self.solution = solution

        return all_todo_items_solved

    @property
    def obs(self):
        observation = ""
        for todo_item_status in self.todo_items_status:
            observation += todo_item_status.obs + "\n"
        return observation
    
class TODOItemStatus(Observable):
    """ todo item status including todo item itself and its solution
    
    Args:
        todo_item(TODOItem): todo item
        solution(Optional[str]): todo item solution. Default to None.
    """

    NOT_SOLVED = "It hasn't been solved yet."

    def __init__(self, todo_item:TODOItem):
        self.todo_item = todo_item
        self.solution:Optional[str] = None

    def solved(self) -> bool:
        """ todo item is solved
        
        Args:
            solution(str): solution of todo item
        
        Returns:
            bool: whether solved
        """
        
        return True if self.solution else False

    @property
    def obs(self) -> str:
        solution = "Solution: {self.solution}" if self.solution else TODOItemStatus.NOT_SOLVED
        return repr(self.todo_item) + "\n" + f"  {solution}"