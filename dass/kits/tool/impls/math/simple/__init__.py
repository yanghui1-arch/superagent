from ....base import tool

@tool
def add(a:int|float, b:int|float) -> int | float:
    """ add a and b

    Args:
        a(int|float): be added
        b(int|flaot): to add
    
    Returns:
        int: result of a + b
    """
    return a + b

@tool
def mul(a:int|float, b:int|float) -> float:
    """ multiply a and b
    
    Args:
        a(int|float): to be multiplied
        b(int|float): to multiply
    """

    return float(a * b)

@tool
def div(a:int|float, b:int|float) -> float:
    """ calculate a/b result
    
    Args:
        a(int|float): to be divided
        b(int|float): devision number. b cannot be 0. if passing 0 will raise ValueError.
    
    Returns:
        float: result of a/b
    """
    assert b != 0, "Don't pass b=0 to div tool."
    return float(a / b)

@tool
def sub(a:int|float, b:int|float) -> float:
    """ calculate a - b result 
    
    Args:
        a(int|float): to be subed
        b(int|float): sub number
    
    Returns:
        float: result of a - b
    """
    
    return float(a - b)