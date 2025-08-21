class ParseError(Exception):
    """ Parse error
    A special error for paring llm output such as its tool calling json and something we want to llm output format
    """
    
    def __init__(self, *args):
        super().__init__(args)