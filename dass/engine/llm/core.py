from typing import Optional, Union
from pydantic import BaseModel
from openai import OpenAI, AsyncOpenAI
from openai.types.chat import ChatCompletion
from opik import track

from ..message import Message

class LLMGenParams(BaseModel):
    stream: bool = False
    stream_options: Optional[dict]
    temperature: Optional[float]
    top_p: Optional[float]
    top_k: Optional[int]
    presence_penalty: Optional[float]
    response_format: Optional[dict]
    
class LLM(BaseModel):
    base_url: str
    api_key: str
    model: str
    client: Optional[OpenAI] = None
    async_client: Optional[AsyncOpenAI] = None

    class Config:
        arbitrary_types_allowed = True

    def model_post_init(self):
        self.async_client:AsyncOpenAI = AsyncOpenAI(base_url=self.base_url, api_key=self.api_key)
        self.client:OpenAI = OpenAI(base_url=self.base_url, api_key=self.api_key)
         
    @track
    async def generate(self, prompts:list[Message], params:LLMGenParams, asynchronous:bool=False) -> Union[str, ChatCompletion]:
        if not asynchronous:
            return self._generate_sync(prompts=prompts, params=params)
        return await self._generate_async(prompts=prompts, params=params)

    def _generate_sync(self, prompts:list[Message], params:LLMGenParams) -> str:
        _prompts = [prompt.model_dump(exclude_none=True) for prompt in prompts]
        _params = params.model_dump(exclude_none=True)
        return self.client.chat.completions.create(messages=_prompts,
                                                   model=self.model,
                                                   **_params)

    async def _generate_async(self, prompts:list[Message], params:LLMGenParams) -> ChatCompletion:
        _prompts = [prompt.model_dump(exclude_none=True) for prompt in prompts]
        _params = params.model_dump(exclude_none=True)
        return await self.async_client.chat.completions.create(messages=_prompts,
                                                               model=self.model,
                                                               **_params)