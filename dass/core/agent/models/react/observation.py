from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional
from .plan import Plan, SubPlan, TODOList, TODOItem
from .action import Action
from .....kits.tool import ToolResult, ResultFlag

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
        self.history_action_status = HistoryActionStatus()
    
    @property
    def obs(self):
        return f"""Plan Observation: 
        {self.plan_status.obs}
        
        Action Observation:
        {self.history_action_status.obs}
        """
    
    @property
    def plan_obs(self):
        return f"""Plan observation:
        {self.plan_status.obs}
        """

    @property
    def action_obs(self):
        return f"""Following observations are result from which action you take before.
        {self.history_action_status.obs}
        """

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

    def __init__(self, subplan:SubPlan, solution:str|None=None):
        self.subplan = subplan
        self.solution:str|None = solution
        self.todo_list_status = None
        self._process:list[ActionStatus] = []
        if subplan.todo_list:
            self.todo_list_status = TODOListStatus(todo_list=subplan.todo_list)

    def solved(self) -> bool:
        return not(self.solution is None and (self.todo_list_status is None or not self.todo_list_status.solved()))
    
    def append_process(self, process:"ActionStatus"):
        """ Append a process into _process list 
        
        Args:
            process(ActionStatus): a process to solve the subplan.
        """

        self._process.append(process)

    @property
    def solve_process(self):
        """ solution process through tools """

        if len(self._process) == 0:
            return "Not use any tool to solve the subplan."

        if self.subplan.completed:
            complete_str = "Complete!"
            process = complete_str + "\n" + "\n".join([f"{i} Step: \n" + p.obs for i, p in enumerate(self._process)])
            process += "\n" + f"solution: {self.solution}"
        else:
            complete_str = "It's in progress maybe..."
            process = complete_str + "\n" + "\n".join([f"{i} Step: \n" + p.obs for i, p in enumerate(self._process)])
        
        return process

    @property
    def obs(self) -> str:
        if not self.todo_list_status:
            if self.solution:
                return self.solution
            if self._process:
                return self.solve_process
            return SubplanStatus.NOT_SOLVED

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
        self.solution:str|None = None
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
    
class HistoryActionStatus(Observable):
    """Record all history actions execution information
    
    Args:
        subplans_actions_hist(list[ActionStatus]): a list of action status. Default to `[]`.
    """

    def __init__(self):
        self.subplans_actions_hist:dict[str, list[ActionStatus]] = {}

    def append(self, subplan_detailed_info:str, action_status:"ActionStatus"):
        if not subplan_detailed_info in self.subplans_actions_hist.keys():
            self.subplans_actions_hist[subplan_detailed_info] = []
        self.subplans_actions_hist[subplan_detailed_info].append(action_status)

    def get_subplan_actions_obs(self, subplan_detailed_info:str) -> str:

        if subplan_detailed_info in self.subplans_actions_hist.keys():
            actions_status_list = self.subplans_actions_hist[subplan_detailed_info]
            return '\n'.join([action_status.obs for action_status in actions_status_list])
        raise KeyError(f"Passing an un-existing key to HistoryActionStatus: {subplan_detailed_info}")

    @property
    def obs(self):
        _obs = ""
        for subplan, action_status_list in self.subplans_actions_hist.items():
            _title = f"Subplan: {subplan.detailed_info}"
            _actions = '\n'.join([f'{i}. {action_status.obs}' for i, action_status in enumerate(action_status_list)])
            _complete_subplan_action_info = _title + '\n' + _actions
            _obs += _complete_subplan_action_info
        return _obs

class ActionStatus(Observable):

    def __init__(self, target_task:str, action:Action, execution_result:ToolResult):
        super().__init__()
        self.target_task = target_task
        self.action = action
        self.execution_result:ToolResult = execution_result
        self.execution_time = datetime.now()

    @property
    def obs(self):
        result_detailed_information = ""
        if self.execution_result.code == ResultFlag.SUCCESS:
            result_detailed_information = f"Action is executed successfully. The result of action is {self.execution_result.msg}"
        elif self.execution_result.code == ResultFlag.NOT_ENOUGH_PARAMS:
            result_detailed_information = f"Failed to execute. Reason: not enough parameters. Detailed information: {self.execution_result.msg}"
        elif self.execution_result == ResultFlag.PARSE_FAILED:
            result_detailed_information = f"Failed to execute. Reason: output cannot be parsed as json format data to pass. Detailed information: {self.execution_result.msg}"
        else:
            result_detailed_information = f"Failed to execute. Detailed information: {self.execution_result.msg}"

        return f"""Action name: {self.action.name}.
        Action parameters: {self.action.tool_params} 
        Result: {result_detailed_information}
        """
