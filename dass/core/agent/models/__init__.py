from uuid import UUID
from uuid import uuid4
from typing import Optional, Literal, ClassVar
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

    def complete(self) -> bool:
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
        completed_cnt(int): TODOItem counts that have been completed. Default to 0.
        no_completed_cnt(int): TODOItem counts that have not completed. Default to 0.
    """

    plan_list: list[TODOItem]
    completed_cnt: int = 0
    no_completed_cnt: int = 0

    def model_post_init(self, context):
        """ initialize counts based on todo list """
        self.no_completed_cnt = sum(1 for item in self.plan_list if item.status == "no-completed")
        self.completed_cnt = len(self.plan_list) - self.no_completed_cnt
    
    def complete_plan(self, todo_item_idx:int) -> bool:
        """ update todo item status and completed, no-completed counts

        Args:
            todo_item_idx(int): index of todo item. NOT order!! MUST be idx!!

        Returns:
            bool: whether complete succussfully
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
        return completed

    @property
    def completed_cnt(self):
        return self.completed_cnt

    @property
    def no_completed_cnt(self):
        return self.no_completed_cnt

class Plan(BaseModel):
    """ Plan is a complete solution for a user question in a whole.
    user_question -> a planlist -> decompose lots of todo lists -> solve items one by one -> back to todo lists -> summarize the observations -> judge whether solve the user question
    Super agent will decompose a big plan to some smaller sub-plans and then make a todo list for these plans.


    Args:
        overall_goal(str): final target. all following arguments are generated based on target
        steps(dict[str, bool]): smaller steps to achive overall goal. Key is the subplans description. Value is whether completed
        completed(bool): whether plan is completed. Default to False.
    """

    COMPLETED_TAG:ClassVar[str] = COMPLETED_TAG
    NO_COMPLETED_TAG:ClassVar[str] = NO_COMPLETED_TAG

    overall_goal: str
    steps: dict[str, bool]
    completed: bool = False

    @property
    def subplans(self) -> list:
        return [sub_plan for sub_plan, _ in self.steps.items()]
    
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