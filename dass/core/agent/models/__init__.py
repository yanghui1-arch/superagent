from pydantic import BaseModel
from .react.action import Action
from ....kits.tool import ToolResult, ResultFlag

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