from typing import Optional, Union, List
from pydantic import BaseModel
from openai import OpenAI, AsyncOpenAI
from openai.types.chat import ChatCompletion
from openai.types.chat.chat_completion_message_function_tool_call import ChatCompletionMessageFunctionToolCall
from opik import track

from ..message import Message, ParsedToolFunction
from ..message import convert_args_to_json
from ...kits.tool import Tool

class LLMGenParams(BaseModel):
    stream: bool = False
    stream_options: Optional[dict] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    presence_penalty: Optional[float] = None
    response_format: Optional[dict] = None
    
class LLM(BaseModel):
    base_url: str
    api_key: str
    model: str
    client: Optional[OpenAI] = None
    async_client: Optional[AsyncOpenAI] = None

    class Config:
        arbitrary_types_allowed = True

    def model_post_init(self, context):
        self.async_client:AsyncOpenAI = AsyncOpenAI(base_url=self.base_url, api_key=self.api_key)
        self.client:OpenAI = OpenAI(base_url=self.base_url, api_key=self.api_key)
         
    @track
    async def generate(
        self,
        prompts:list[Message],
        params:LLMGenParams,
        tools:Optional[list[Tool]]=None,
        asynchronous:bool=False
    ) -> Union[str, list[ParsedToolFunction], ChatCompletion]:
        """ generate response from llm and track with opik
        It's forbidden to pass `params.stream=True` and `tools=[...]` at the same time because streamly parse tool function is more complex than stream=False.
        Streamly accept tools and parse tool will be supported in the later version.

        Args:
            prompts(list[Message]): prompts list
            params(LLMGenParams): generation parameters
            tools(Optional[list[Tool]]): a list available tools that llm can calling. Default to None.
            asynchronous(bool): whether async calling. Default to Falase

        Returns:
            Union[str, list[ParsedToolFunction], ChatCompletion]: return ChatCompletion if it's async else return str or a list of ParsedToolFunction. 
        """

        if params.stream and asynchronous:
            raise ValueError("Not support streamly calling llm.generate function now. Please do not pass `params.stream=True` and `tools=[...]` in the same time.")

        if tools:
            tools = [tool.to_openai_format_dict() for tool in tools]
        if not asynchronous:
            return self.generate_sync(prompts=prompts, tools=tools, params=params)
        return await self.generate_async(prompts=prompts, params=params)

    @track
    def generate_sync(
        self,
        prompts:list[Message],
        params:LLMGenParams,
        tools:Optional[list[dict[str, str|dict]]]=None
    ) -> str | list[ParsedToolFunction]:
        """ generate response sync
        
        Args:
            prompts(list[Message]): prompts to pass llm
            params(LLMGenParams): llm generation parameters.
            tools(Optional[list[dict]]): a list of available tools which satisfies openai tool call format
        
        Returns:
            str: llm response
            list[ParsedToolFunction]: a list of parsed tool function
        """
        print(tools)
        _prompts = [prompt.model_dump(exclude_none=True) for prompt in prompts]
        _params = params.model_dump(exclude_none=True)
        completion:ChatCompletion = self.client.chat.completions.create(
            messages=_prompts,
            model=self.model,
            tools=tools,
            parallel_tool_calls=True,
            **_params
        )
        _is_using_tool = completion.choices[0].message.tool_calls != None
        # parse tool calling name and passing parameters
        if _is_using_tool:
            tool_calls:List[ChatCompletionMessageFunctionToolCall] = completion.choices[0].message.tool_calls
            parsed_tool_calls:List[ParsedToolFunction] = []
            for tool_call in tool_calls:
                func = tool_call.function
                parsed_tool_function:Optional[ParsedToolFunction] = convert_args_to_json(func_name=func.name, args=func.arguments)
                if parsed_tool_function is not None:
                    parsed_tool_calls.append(parsed_tool_function)
                else:
                    print(f"func[{func.name}] arguments is invalid and cannot be parsed into json: {func.arguments}")
            return parsed_tool_calls
        
        else:
            # str
            return completion.choices[0].message.content


    @track
    async def generate_async(self, prompts:list[Message], params:LLMGenParams) -> ChatCompletion:
        _prompts = [prompt.model_dump(exclude_none=True) for prompt in prompts]
        _params = params.model_dump(exclude_none=True)
        return await self.async_client.chat.completions.create(messages=_prompts,
                                                               model=self.model,
                                                               **_params)