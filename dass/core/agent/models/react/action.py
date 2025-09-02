from uuid import uuid4
from uuid import UUID
from typing import Optional
from pydantic import BaseModel
from .....kits.tool import Tool, ToolResult

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