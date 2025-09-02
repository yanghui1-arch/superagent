from abc import ABC, abstractmethod
from uuid import UUID
from uuid import uuid4
from typing import Optional, Literal, ClassVar, List
from pydantic import BaseModel
from ....kits.tool import Tool, ToolResult, ResultFlag
from ...prompts import NO_COMPLETED_TAG, COMPLETED_TAG

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
        completed = todo_item.complete()
        if completed:
            self.completed_cnt += 1
            self.no_completed_cnt -= 1

        if self.no_completed_cnt < 0:
            print(f"[WARNING]: no-completed count is below 0 when complete plan.")
        return self

    @property
    def todo_items(self) -> list[TODOItem]:
        return self.plan_list

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
    completed: bool = False

    def model_post_init(self, context):
        self.subplans:list[SubPlan] = []

    @property
    def subplans_desc(self) -> list[str]:
        return [sub_plan for sub_plan, _ in self.steps.items()]
    
    @property
    def subplans_detailed(self) -> list["SubPlan"]:
        return self.subplans

    @property
    def steps(self) -> dict[str, bool]:
        return self.steps
    
    @property
    def steps_detailed(self) -> str:
        detailed_info = ""
        for subplan, complete in self.steps.items():
            detailed_info += f"{Plan.COMPLETED_TAG if complete else Plan.NO_COMPLETED_TAG} {subplan} \n"
        return detailed_info

    @property
    def completed(self):
        return self.completed

class SubPlan(BaseModel):
    """ sub plan class
    Super agent will make a plan, including lots of subplans, for a question. Super agent doesn't make any todo list during this time. So Plan.steps only includes a subplan description.
    `SubPlan` class emerges at this time. It solves how super agent can do to achive the subplan

    Args:
        detailed_info(str): detailed information about the subplan.
        todo_list(Optional[TODOList]): todo list to achive subplan. Default to None.
    """

    detailed_info: str
    todo_list: Optional[TODOList] = None

    def __repr__(self):
        todo_list:list[str] = []
        if self.todo_list:
            for idx, todo_item in enumerate(self.todo_list.todo_items()):
                todo_list.append(f" {idx}. {todo_item}")
        return f"Subplan: {self.detailed_info}\nTODO List:\n{"\n".join(todo_list)}"

class Action(BaseModel):
    """ Action by agent
    
    Args:
        id(UUID): action id
        tool(Tool): calling tool
        tool_params(Optional[dict]): tool input parameters. Default to None.
    """
    id: UUID = uuid4()
    tool: Tool
    tool_params: Optional[dict] = None

    def __repr__(self):
        return self.tool.name
    
    def act(self) -> ToolResult:
        if self.tool_params:
            return self.tool(**self.tool_params)
        return self.tool()
    
    @property
    def name(self):
        return self.tool.name

class Observation(BaseModel):
    """Observation includes all details about plan.
    Super agent observations boil down to a few options.
    First subplan status, focusing on whether subplan has been solved and how to do it.
    Second todo list status. As designed before, there is a todo list in a subplan which is essential to achieve subplan. So super agent need todo list observations.
    Third todo item status. How to finish todo items one by one and finally achieve a todo list.
    Subplan status is not only todo list status but directly solve the subplan. Due to optional todo list, not every subplan has a todo list. The easy subplan will be solved directly by super agent with tools or just self capabilities.
    """

    plan_status: "PlanStatus"


class Observable(ABC):
    @property
    @abstractmethod
    def obs(self):
        ...

class PlanStatus(Observable):
    """ plan status
    
    Args:
        plan(Plan): plan
        subplan_status_list(list[SubPlanStatus]): all subplans status of the plan
        solution(Optional[str]): plan solution. Default to None
    """

    def __init__(self, plan:Plan):
        self.plan = plan
        self.subplan_status_list:list["SubplanStatus"] = []
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
    
class Enviroment(BaseModel):
    """ Virtual env
    One question corresponds to one enviroment
    
    Args:
        user_input(str): user input question
        tool_output(dict[str, ToolResult]): a chain of tool output log information. Key is action name and value is tool result.
        tool_output_chain(list[dict[str, ToolResult]]): a current chain of tool outputs
        chains_tool_output(dict[str, dict]): all chains of tool output. Key is `chain_{number}` and value is a series of tool_output in one chain.
    """

    user_input: str
    tool_output: dict[str, ToolResult] = {}
    tool_output_chain: list[dict[str, ToolResult]] = []
    chains_tool_output: dict[str, list[dict]] = {}

    def reset(self):
        """ env reset
        Save the tool output of current chain if it's not empty.
        Future feature: Write the chains of tool output into a special file for later check.
        """

        if self.tool_output_chain:
            self.save_chain()

        # future feat: need to log all self.chains_tool_output and redirect content to a specialized file. 

        # empty
        self.tool_output = {}
        self.tool_output_chain = []
        self.chains_tool_output = {}
    
    def get_all_obs(self):
        """ get all rounds of chains_tool_output """
        
        return f"""User input: `{self.user_input}`.\n
        The following is your chains of calling tools execution results.
        \n
        {str(self.chains_tool_output)}
        \n
        The element of the dict is a dict[str, [dict[str, ToolResult]]] type. Key is chain rounds and value is a series of tool outputs.
        We consider it as a series of calling tools in one chain. And the `str` of the series of calling tool is tool_name
        and `ToolResult` is result of calling this tool.\n
        ToolResult includes a code and a message. If code is not SUCCESS the msg is exception information. Otherwise msg is tool output message.\n
        """
    
    def step(self, action:Action) -> str:
        """ take one action
        
        Args:
            action(Action): take action
        
        Return:
            str: observation after calling action
        """

        name = action.name
        try:
            result:ToolResult = action.act()
            self.tool_output[name] = result
        except Exception as e:
            self.tool_output[name] = ToolResult(code=ResultFlag.ERROR, msg=e)
        finally:
            self.tool_output_chain.append(self.tool_output)
            return self._get_obs()
        
    def save_chain(self):
        """ save the chain tool output
        Save self.tool_output_chain into the whole chains of tool output and reinitialize the current chain of tool output.
        """

        key = self._chain_key(chain_len=len(self.chains_tool_output.keys()))
        self.chains_tool_output[key] = self.tool_output_chain
        self.tool_output_chain = []

    def _chain_key(self, chain_len:int):
        """ standard chains_tool_output key format 
        
        Args:
            chain_len(int): current chains length. ususally access by len(self.chains_tool_output.keys())
        """

        return f"chain_{chain_len}"
    
    def _get_obs(self) -> str:
        """ get current observation """

        return f"""User input: `{self.user_input}`.\n
        The following <tool_output> is output by using {self.tool_output.keys()[0]} tool.\n
        <tool_output> \n
        {str(self.tool_output)} \n
        </tool_output>\n
        The element of the dict is a dict[str, ToolResult] type. Key is action name and value is ToolResult.\n
        ToolResult includes a code and a message. If code is not SUCCESS the msg is exception information. Otherwise msg is tool output message.\n
        """