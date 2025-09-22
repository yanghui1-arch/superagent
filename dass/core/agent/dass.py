from typing import Optional, Any, ClassVar, List, Dict, Literal
from uuid import UUID
from uuid import uuid4
from ..agent import Agent
from ...engine.llm import Message
from ...engine.llm import LLMGenParams
from .models.react.plan import Plan, SubPlan
from .models.react.action import Action
from .models.react.observation import Observation
from .models.react.observation import SubplanStatus
from .models.result import ThinkResult, ExecutionResult
from ...kits.tool import Tool, ToolResult
from ..prompts import sys_prompt, final_answer_sys_prompt, think_prompt, plan_prompt, start_solve_prologue
from ..prompts import build_think_prompt, build_plan_prompt
from ..prompts import (
    OBSCURE_QUESTION_TAG,
    SOLVED_TAG,
    PLAN_TAG,
    PLAN_END_TAG,
    EASY_TAG,
    EASY_END_TAG
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
        self.final_answer_sys_prompt:Message = Message.system_message(final_answer_sys_prompt)
        
        self.plan:Optional[Plan] = None
        self.observation: Optional[Observation] = None
        self.conversation_uuid: Optional[UUID] = None

    async def run(self, user_input:str) -> str:
        """ agent core execution """
        
        if not self.conversation_uuid:
            # create conversation uuid and init the system prompt.
            print(f"[INFO] {self.__class__.__name__} doesn't have conversation uuid. So create one for her.")
            self.conversation_uuid = uuid4()
            self.context_manager.append(self.conversation_uuid, message=self.system_prompt)
        question:str = user_input
        plan:Plan|str = await self.planning(user_question=question)

        # str means result directly
        if isinstance(plan, str):
            # append assistant message
            self.context_manager.append(conversation_uuid=self.conversation_uuid, message=Message.assistant_message(plan))
            return plan

        self.plan = plan
        answer = await self.complete_plan(plan=plan)
        
        # reset plan to None
        self.plan = None

        return answer

    async def complete_plan(self, plan:Plan):
        """ Super agent finish one plan 
        
        Args:
            plan(Plan): plan to complete

        Returns:
            str: a total overview of plan completion status.
        """

        print(f"[INFO] super agent is completing plan.")
        subplans = plan.subplans

        for idx, subplan in enumerate(subplans):
            final_solution = await self.complete_subplan(subplan=subplan)
            self.context_manager.append(
                conversation_uuid=self.conversation_uuid,
                message=Message.assistant_message(final_solution)
            )

        usr_prompt = f"So tell me the final answer."
        answer:str = await self._request_llm(
            messages=self.context_manager.context(conversation_uuid=self.conversation_uuid) + [Message.user_message(usr_prompt)]
        )
        # append assistant message
        self.context_manager.append(conversation_uuid=self.conversation_uuid, message=Message.assistant_message(answer))
        
        print(f"[INFO] super agent has completed plan.")
        return answer

    async def complete_subplan(self, subplan:SubPlan) -> str:
        """ complete a subplan
        
        Args:
            subplan(SubPlan): a subplan
        """

        done = False
        final_solution:str|None = None

        while not done:
            # think
            think_res:ThinkResult = await self.think(subplan=subplan)
            # solution
            if think_res.done == True:
                final_solution = think_res.final_answer
                done = think_res.done
            # action & observe
            else:
                for action in think_res.actions:
                    tool_result:ToolResult = action.act()
                    # append tool message
                    print(f"tool call id: {action.tool_call_id}, content: {tool_result.msg}, type: {type(tool_result.msg)}")
                    self.context_manager.append(
                        conversation_uuid=self.conversation_uuid, 
                        message=Message.tool_message(content=tool_result.msg, tool_call_id=action.tool_call_id)
                    )
                    
        return final_solution


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

        plan_prompt_str = build_plan_prompt(user_question=user_question)
        plan_prompt_msg = Message.user_message(plan_prompt_str)
        # append user message
        self.context_manager.append(conversation_uuid=self.conversation_uuid, message=plan_prompt_msg)
        _plan:str = self.llm.generate_sync(
            prompts=self.context_manager.context(conversation_uuid=self.conversation_uuid), 
            params=self.llm_gen_params
        )
        # append assistant message
        self.context_manager.append(
            conversation_uuid=self.conversation_uuid,
            message=Message.assistant_message(content=_plan)
        )

        if not isinstance(_plan, str):
            raise TypeError(f"Expected `str` type but return `{type(_plan)}` type when super agent make plans.")
        
        print(_plan)
        # solve directly.
        if EASY_TAG in _plan and SOLVED_TAG in _plan:
            # calculation function is decided by prompt designs.
            solved_idx = _plan.find(SOLVED_TAG)
            start_idx = solved_idx + len(SOLVED_TAG)
            end_tag_len = len(EASY_END_TAG)
            result = _plan[start_idx: -end_tag_len]

            print(f"[INFO] super agent has successfully solve the question.")
            return result
        # make a plan
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
        subplan:SubPlan
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

        _selection: Optional[Literal['solved', 'obscure', 'call_tool']] = None
        _actions:List[Action] = []
        _done = False
        _final_answer:Optional[str] = None
        
        # TODO: update for lower prompt words 
        _think_prompt = build_think_prompt(subplan=subplan)
        self.context_manager.append(self.conversation_uuid, message=Message.user_message(content=_think_prompt))

        response = await self.llm.generate(
            self.context_manager.context(conversation_uuid=self.conversation_uuid),
            LLMGenParams(temperature=0.8),
            tools=self.available_tools
        )
        print(f"[INFO]: Super agent think content:\n{response}")

        # Actions that super agent calling tools directly
        # tool message is appended outsider
        if isinstance(response, tuple):
            _selection = 'call_tool'
            parse_tool_functions = response[0]
            tool_calls = response[1]

            # append a calling assistant message
            self.context_manager.append(conversation_uuid=self.conversation_uuid, message=Message.assistant_message(content=None, tool_calls=tool_calls))

            for tool in parse_tool_functions:
                match_tool:Tool = [_tool for _tool in self.available_tools if _tool.name == tool.name][0]
                args = tool.arguments
                _actions.append(Action(tool_call_id=tool.tool_call_id, tool=match_tool, tool_params=args))
        
        # not calling tool -> solve directly or raise an obscure information.
        elif isinstance(response, str):
            # append assistant message
            self.context_manager.append(
                conversation_uuid=self.conversation_uuid,
                message=Message.assistant_message(content=response)
            )
            parsed_result:ThinkResult = self._parse_think(think_response=response)
            _selection = parsed_result.selection
            _final_answer = parsed_result.final_answer
            _done = parsed_result.done

        return ThinkResult(
            selection=_selection,
            actions=_actions,
            done=_done,
            final_answer=_final_answer
        )

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

    def _parse_think(self, think_response:str) -> ThinkResult:
        """ parse think content
        CANNOT parse tool calling action. Passing think before ensuring the think content is not tool calling
        Super agent has several selections during thinking. The function is to parse the think reponse and try to parse
        which selection super agent choose.
        NOTICE: I dont find a good method of how super agent output fix content and how to parse it.
        
        Args:
            think(str): think content which is not tool calling

        Returns:
            ThinkResult: think result

        Raises:
            ValueError: if think_response is in invalid format
        """           

        # select first
        if SOLVED_TAG in think_response:
            start_idx = think_response.find(SOLVED_TAG) + len(SOLVED_TAG)
            final_answer = think_response[start_idx:]
            return ThinkResult(selection="solved", done=True, final_answer=final_answer) 
        
        # select third
        elif OBSCURE_QUESTION_TAG in think_response:
            start_idx = think_response.find(OBSCURE_QUESTION_TAG) + len(OBSCURE_QUESTION_TAG)
            obscure_info = think_response[start_idx:]
            return ThinkResult(selection="obscure", done=True, final_answer=obscure_info)

        raise ValueError("Super agent think response is not in a valid format. Try to make super agent think again with different llm_gen_params.")

    async def _request_llm(self, messages:list[Message], tools=None):
        """ request a list of message to llm """
        
        if tools is None:
            return await self.llm.generate(
                messages,
                LLMGenParams(temperature=0.8)
            )
        return await self.llm.generate(
            messages,
            LLMGenParams(temperature=0.8),
            tools=self.available_tools
        )

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