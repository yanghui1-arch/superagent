# Tool

## How to convert a function to a Tool instance
Use `@tool` to convert a function to Tool instance just do as following. 
```
@tool
def get_weather(city: str, town:Optional[str]=None) -> str:
    """ get weather of a town in a ctiy if town is provided otherwise just city weather.
    
    Args:
        city(str): city name
        town(Optional[str]): town name. Default to None
    """
    return f"Sunny in {town if town else ""} {city}."
```
Notice:
1. function docstring should be take in two parts. One is introduction of the function. Another is to tell us the parameter name, annotation and description. They are splitted by a line. It's important!
2. clear to introduction how the function does.