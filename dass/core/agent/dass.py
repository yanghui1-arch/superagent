from typing import Optional, Any, ClassVar, List, Dict
from queue import Queue
from ..agent import Agent
from ...engine.llm import Message
from ...engine.message import ParsedToolFunction
from ...engine.llm import LLMGenParams
from .models.react.plan import Plan, SubPlan, TODOList, TODOItem
from .models.react.action import Action
from .models.react.observation import Observation
from .models.react.observation import PlanStatus, SubplanStatus, TODOItemStatus, ActionStatus
from .models.result import ThinkResult, ParsedThinkResult, ExecutionResult
from ...kits.tool import Tool
from ..prompts import sys_prompt, think_prompt, plan_prompt
from ..prompts import build_think_prompt
from ..prompts import (
    OBSCURE_QUESTION_TAG,
    SOLVED_TAG,
    PLAN_TAG,
    PLAN_END_TAG,
    EASY_TAG,
    EASY_END_TAG,
    TODO_LIST_TAG,
    NO_COMPLETED_TAG,
    COMPLETED_TAG,
    ORDER_START_TAG,
    ORDER_END_TAG,
    ANALYZE_START_TAG,
    ANALYZE_END_TAG,
    DECOMPOSE_START_TAG,
    DECOMPOSE_END_TAG,
    MAKE_TODO_LIST_START_TAG,
    MAKE_TODO_LIST_END_TAG,
    TODO_ITEM_START_TAG,
    TODO_ITEM_END_TAG
)
from ...config.load import load_llm_config, load_embedding_config


class SuperAgent(Agent):
    """ SuperAgent, a daily life assistant who can not only tackle trivial troubles but also solve the big problem. 
    
    Args:
        MAX_CALLING_TOOLS_IN_ONE_CHAIN(ClassVar[int]): max tools calling counts in one chain.
        MAX_CALLING_CHAINS(ClassVar[int]): max chains of answering one question.

        plan(Optional[Plan]): current plan to answer user question. Default to None.
        current_calling_tools_cnt(int): current calling tools count. Default to 0.
        current_chains(int): current chains number. Default to 0.
        available_tools(Optional[list[Tool]]): all available tools that can be called by Dass. Default to None.
        system_prompt(Optional[Message]): system prompt of super agent only exist when available_tools is not None. Default to None.
    """
    
    MAX_CALLING_TOOLS_IN_ONE_CHAIN: ClassVar[int] = 35
    MAX_CALLING_CHAINS: ClassVar[int] = 10

    available_tools: Optional[list[Tool]] = None

    def model_post_init(self, context):
        """ convert available_tools -> system prompt """
        
        super().model_post_init(context)
        self.currrent_calling_tools_cnt: int = 0
        self.current_chains: int = 0
        
        if self.available_tools:
            sys_str = sys_prompt.format(name=self.__class__.__name__, available_tools=self._format_tool_list(self.available_tools))                
            self.system_prompt:Message = Message.system_message(sys_str)
        
        self.plan:Optional[Plan] = None
        self.observation: Optional[Observation] = None

    async def run(self, user_input:str) -> Any:
        """ agent core execution """
        
        question:str = user_input
        plan:Plan|str = await self.planning(user_question=question)

        # str means result directly
        if isinstance(plan, str):
            return plan

        self.plan = plan
        self.observation = Observation(plan=plan)

        plan_status_obs:str = await self.complete_plan(plan=plan)
        ass_prompt = f"I can make a plan to answer your question. And here is my plan and its completion status.\n{plan_status_obs}"
        usr_prompt = f"I have known your plan and it's good. Now you can answer me question based on your plan status."

        answer = await self._request_llm(messages=[self.system_prompt, Message.user_message(user_input), Message.assistant_message(ass_prompt), Message.user_message(usr_prompt)])
        
        # reset plan to None
        self.plan = None
        self.observation = None

        return answer

    async def complete_plan(self, plan:Plan) -> str:
        """ Super agent finish one plan 
        
        Args:
            plan(Plan): plan to complete

        Returns:
            str: a total overview of plan completion status.
        """

        print(f"[INFO] super agent is completing plan.")
        subplans = plan.subplans
        for subplan in subplans:
            done = False
            solution = None
            # get subplan status
            subplan_status = [
                _subplan_status 
                for _subplan_status in self.observation.plan_status.subplan_status_list 
                if _subplan_status.subplan.detailed_info == subplan.detailed_info
            ][0]

            while not done:
                execution_res:ExecutionResult = await self.execute(subplan=subplan, subplan_status=subplan_status)
                done = execution_res.done
                solution = execution_res.final_answer
            subplan_status.solution = solution
        
        print(f"[INFO] super agent has completed plan.")
        return self.observation.plan_status.obs

    async def execute(self, subplan:SubPlan, subplan_status:SubplanStatus) -> ExecutionResult:
        """ Execute Observation -> Think -> Action once
        It focus on a small subplan and result is also for subplan
        
        Args:
            subplan(Subplan): subplan of plan
            subplan_status(SubplanStatus): subplan status
        """
        print(f"[INFO] Start executing subplan...: \n    {subplan.detailed_info}")

        print(f"[DEBUG] observations: {subplan_status.obs}")
        think_result:ThinkResult = await self.think(
            subplan_instance=subplan,
            subplan_status=subplan_status,
            observations=subplan_status.obs
        )

        # record action observations
        for action in think_result.actions:
            res = action.act()
            action_status = ActionStatus(target_task=subplan.detailed_info, action=action, execution_result=res)
            self.observation.history_action_status.append(subplan_detailed_info=subplan.detailed_info, action_status=action_status)
            subplan_status.solution = self.observation.history_action_status.get_subplan_actions_obs(subplan_detailed_info=subplan.detailed_info)

        # other
        if think_result.selection == "make_todo_list":
            assert self.plan, "Failed to make todo list because somewhere calls SuperAgent.execute() but not any plan."
            subplan.todo_list = think_result.subplan.todo_list
        elif think_result.selection == "analyze":
            # decompose a todo item into smaller subplan with a todo list.
            # it will be executed successfully here
            if think_result.subplan:
                exec_res:ExecutionResult = await self.execute(subplan=think_result.subplan, subplan_status=SubplanStatus(subplan=think_result.subplan))
                return exec_res
            # super agent select one todo item and directly solve it without any tools.
            else:
                ...
        
        print(f"[INFO] subplan: {subplan.detailed_info} DONE: {think_result.done}")
        print(f"[INFO] End execute subplan...: {subplan.detailed_info}")
        return ExecutionResult(done=think_result.done, final_answer=think_result.final_answer)


    async def planning(self, user_question:str) -> Plan | str:
        """ Super agent plan process
        Super agent plan first and then list all subplans and relative todo lists to solve user question.

        Args:
            user_question(str): user question

        Returns:
            Plan: plan that super agent makes
            str: result because it's easy for super agent
        """

        print(f"[INFO] Try to solve the `{user_question}`. If cannot solve it directly, super agent will switch to make a plan.")

        plan_prompt_str = plan_prompt.format(
            user_question=user_question,
            PLAN_TAG=PLAN_TAG,
            PLAN_END_TAG=PLAN_END_TAG,
            EASY_TAG=EASY_TAG,
            EASY_END_TAG=EASY_END_TAG,
            NO_COMPLETED_TAG=NO_COMPLETED_TAG,
            SOLVED_TAG=SOLVED_TAG
        )
        plan_prompt_msg = Message.user_message(plan_prompt_str)
        _plan:str = self.llm.generate_sync(prompts=[self.system_prompt, plan_prompt_msg], params=self.llm_gen_params)

        if not isinstance(_plan, str):
            raise TypeError(f"Expected `str` type but return `{type(_plan)}` type when super agent make plans.")
        
        print(_plan)
        if EASY_TAG in _plan and SOLVED_TAG in -1:
            # calculation function is decided by prompt designs.
            solved_idx = _plan.find(SOLVED_TAG)
            start_idx = solved_idx + len(SOLVED_TAG)
            end_tag_len = len(EASY_END_TAG)
            result = _plan[start_idx: -end_tag_len]

            print(f"[INFO] super agent has successfully solve the question.")
            return result
        else:
            if PLAN_TAG not in _plan:
                raise ValueError(f"Super agent plan generation is not expected without {PLAN_TAG}.")
            # plus one due to colon and \n
            plan_tag_start_idx = _plan.find(PLAN_TAG)
            start_idx = plan_tag_start_idx + len(PLAN_TAG) + 2
            subplans:List[str] = _plan[start_idx:-len(PLAN_END_TAG)].splitlines()
            steps:Dict[str, bool] = {}
            subplan_instance_list = []
            for subplan in subplans:
                steps[subplan] = False
                subplan_instance_list.append(SubPlan(detailed_info=subplan))

            print(f"[INFO] super agent cannot solve the question directly so she makes a plan.")
            return Plan(overall_goal=user_question, steps=steps, subplans=subplan_instance_list)

    async def think(
        self,
        subplan_instance:SubPlan,
        subplan_status:SubplanStatus,
        observations:Optional[str]=None,
    ) -> ThinkResult:
        """ Super agent think
        Include four strategies: make a to-do list, choose tools, break question into small tasks or give the final answer.
        Think whether the subplan canbe decomposed deeper and then return a subplan if it can else should return a list of actions or a final answer.
        Todo item status will be changed when super agent tries to solve a selected todo item which will have a big influence on `subplan_status`.

        Args:
            subplan_instance(SubPlan): sub plan
            observations(Optional[str]): observations now
        
        Returns:
            ThinkResult: super agent views for a subplan includes its selection, subplan, terminate, actions list and final answer
        """

        subplan:str = subplan_instance.detailed_info
        todo_list:Optional[TODOList] = subplan_instance.todo_list

        _selection: Optional[str] = None
        _actions:List[Action] = []
        _subplan:Optional[SubPlan] = None
        _done = False
        _final_answer:Optional[str] = None
        
        observations = "" if not observations else observations
        _think_prompt = build_think_prompt(
            subplan=subplan,
            observations=observations,
            todo_list=todo_list
        )
        response = await self.llm.generate(
            [self.system_prompt, Message.user_message(_think_prompt)], 
            LLMGenParams(temperature=0.8),
            tools=self.available_tools
        )
        print(f"[INFO]: Super agent think content:\n{response}")

        # Actions that super agent calling tools directly
        if isinstance(response, list):
            for tool in response:
                match_tool:Tool = [_tool for _tool in self.available_tools if _tool.name == tool.name][0]
                args = tool.arguments
                _actions.append(Action(tool=match_tool, tool_params=args))
        
        # not calling tool
        elif isinstance(response, str):
            parsed_result:ParsedThinkResult = self._parse_think(think=response)
            _selection = parsed_result.selection
            if parsed_result.selection == "make_todo_list":
                _subplan = SubPlan(detailed_info=subplan, todo_list=parsed_result.info)
            elif parsed_result.selection == "solved" or parsed_result.selection == "obscure":
                _final_answer = parsed_result.info
            # select analyze
            # decompose
            elif isinstance(parsed_result.info, TODOList):
                _subplan = SubPlan(detailed_info=parsed_result.selected_todo_item, todo_list=parsed_result.info)
            # solve one todo item to solve
            else:
                assert todo_list, "not pass todo list when try to analyze the subplan."
                assert subplan_status.todo_list_status is not None, f"The subplan `{subplan}` doesn't have any todo list so that cannot change the status. Please make sure SubplanStatus includes todo list status."
                selected_todo_item_str = parsed_result.selected_todo_item
                todo_item:TODOItem = next((todo_item for todo_item in todo_list.todo_items() if todo_item.content == selected_todo_item_str))
                now_todo_list = self._complete_todo_item(todo_list=todo_list, completing_todo_item=todo_item)
                todo_item_status:TODOItemStatus = subplan_status.todo_list_status.index(todo_item=todo_item)
                todo_item_status.solution = parsed_result.info
                print(f"[INFO] Latest todo list: {now_todo_list}")

            _done = parsed_result.done

        return ThinkResult(
            selection=_selection,
            subplan=_subplan,
            actions=_actions,
            done=_done, 
            final_answer=_final_answer
        )

    def _complete_todo_item(self, todo_list:TODOList, completing_todo_item:TODOItem) -> TODOList:
        """ complete a todo item of todo list
        Find the completing todo item in a todo list and mark it as completed with markdown format. 

        Args:
            todo_list(TODOList): todo list
            completing_todo_item(TODOItem): completing todo item
        
        Returns:
            TODOList: current todo list
        """

        try:
            todo_item_idx = todo_list.todo_items.index(completing_todo_item)
            todo_list = todo_list.complete_todo_item(todo_item_idx=todo_item_idx)
        except ValueError as ve:
            print(f"[WARNING]: No {completing_todo_item} in {todo_list}")
        finally:
            return todo_list

    def _format_tool_list(self, tool_list:list[Tool]):
        """ format tool list to a markdown list 
        
        Args:
            tool_list(list[Tool]): list of tools
        """

        formatted_tools = [
            f"{i}. [{tool.name}]: [{tool.description}]"
            for i, tool in enumerate(tool_list)
        ]
        return '\n'.join(formatted_tools)

    def _parse_think(self, think_response:str) -> ParsedThinkResult:
        """ parse think content
        CANNOT parse tool calling action. Passing think before ensuring the think content is not tool calling
        Super agent has several selections during thinking. The function is to parse the think reponse and try to parse
        which selection super agent choose.
        NOTICE: I dont find a good method of how super agent output fix content and how to parse it.
        
        Args:
            think(str): think content which is not tool calling

        Returns:
            ParsedThinkResult: parsed think result

        Raises:
            ValueError: if think_response is in invalid format
        """
        
        # select the first
        if MAKE_TODO_LIST_START_TAG in think_response and TODO_LIST_TAG in think_response:
            todo_list = self._parse_todo_list(think_response)
            return ParsedThinkResult(selection="make_todo_list", info=todo_list)

        # select the second
        elif ANALYZE_START_TAG in think_response:
            # select one not completed todo item
            selected_todo_item:Optional[str] = None
            if think_response.find(TODO_ITEM_START_TAG):
                todo_item_start_idx = think_response.find(TODO_ITEM_START_TAG) + len(TODO_ITEM_START_TAG)
                todo_item_end_idx = think_response.find(TODO_ITEM_END_TAG)
                selected_todo_item = think_response[todo_item_start_idx: todo_item_end_idx]

            # 2.1
            if SOLVED_TAG in think_response:
                solution_start_idx = think_response.find(SOLVED_TAG) + len(SOLVED_TAG)
                solution = think_response[solution_start_idx:-len(ANALYZE_END_TAG)]
                return ParsedThinkResult(selection="analyze", done=False, info=solution, selected_todo_item=selected_todo_item)
            # 2.2
            if DECOMPOSE_START_TAG in think_response and DECOMPOSE_START_TAG in think_response and TODO_LIST_TAG in think_response:
                todo_list = self._parse_todo_list(think_response)
                return ParsedThinkResult(selection="analyze", done=False, info=todo_list, selected_todo_item=selected_todo_item)                

        # select fourth
        elif SOLVED_TAG in think_response:
            start_idx = think_response.find(SOLVED_TAG) + len(SOLVED_TAG)
            final_answer = think_response[start_idx:]
            return ParsedThinkResult(selection="solved", done=True, info=final_answer) 
        
        # select fifth
        elif OBSCURE_QUESTION_TAG in think_response:
            start_idx = think_response.find(OBSCURE_QUESTION_TAG) + len(OBSCURE_QUESTION_TAG)
            return ParsedThinkResult(selection="obscure", done=True, info=think_response[start_idx:])

        raise ValueError("Super agent think response is not in a valid format. Try to make super agent think again with different llm_gen_params.")

    def _parse_todo_list(response:str) -> TODOList:
        """ parse a text with TODO_LIST_TAG 
        The text should include the paragraph texts like following:
        ```
        {TODO_LIST_TAG}
        {NO_COMPLETED_TAG} ... {ORDER_START_TAG}1{ORDER_END_TAG}
        ```
        Row is no-completed todo item if it hasn't order. 

        Args:
            response(str): text with TODO_LIST_TAG
        
        Return:
            TODOList: a todo list
        """

        start_idx = response.find(TODO_LIST_TAG) + len(TODO_LIST_TAG) + 1
        todo_list:List[str] = response[start_idx:].splitlines()
        todo_items = []
        for idx, item in enumerate(todo_list):
            order = idx
            content = item

            if ORDER_START_TAG in item and ORDER_END_TAG in item:
                order_start_idx = item.find(ORDER_START_TAG)
                order_end_idx = item.find(ORDER_END_TAG)
                # to get executing order
                order_str:str = item[order_start_idx + len(ORDER_END_TAG): order_end_idx]
                order = int(order_str.strip())
                # to get item content without order information
                content = item[:order_start_idx]

            todo_item = TODOItem(order=order, content=content)
            todo_items.append(todo_item)
        return TODOList(plan_list=todo_items)

    async def _request_llm(self, messages:list[Message]):
        """ request a list of message to llm """
        
        response = await self.llm.generate(
            messages,
            LLMGenParams(temperature=0.8),
            tools=self.available_tools
        )
        return response

    def request_llm(message:list[Message]):
        ...

    def retrieve_memory(query:str, top_k:int):
        """ retrieve top_k number most relative memories """
        print(3)

if __name__ == "__main__":
    import asyncio
    from ...kits.tool.impls.math.simple import add, sub, div, mul
    async def main():
        llm_config = load_llm_config()
        embedding_config = load_embedding_config()
        dass = SuperAgent(llm_config=llm_config, embedding_config=embedding_config, available_tools=[add, sub, div, mul])
        answer = await dass.run(user_input="(99937 + 2 * 6555) / 3.2 + 1.4 / 2.0 + 44 * 997665 = ?")
        print()
        print("response:\n")
        print(answer)
    asyncio.run(main=main())