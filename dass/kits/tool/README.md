# Tool

## How to convert a function to a Tool instance
Easy to use `@tool` to convert a function to Tool instance.
```python
@tool
def get_weather(city: str, town:Optional[str]=None) -> str:
    """ get weather of a town in a ctiy if town is provided otherwise just city weather.
    
    Args:
        city(str): city name
        town(Optional[str]): town name. Default to None
    """
    return f"Sunny in {town if town else ""} {city}."
```
Then you can call tool easily and check its parameters.
```python
print(get_weather(city="Shanghai"))
print(get_weather.func)
print(get_weather.name)
print(get_weather.description)
print(get_weather.parameters)
```

Notice:
1. function docstring should be take in two parts. One is introduction of the function. Another is to tell us the parameter name, annotation and description. They are splitted by a line. It's important!
2. clear to introduction how the function does.
3. not support tuple now. If you want to support tuple type you can post a request and try to solve it on dass.kits.tool.parse_type_hint.py line 50.