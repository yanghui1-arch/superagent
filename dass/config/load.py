import os
import tomllib
from typing import Dict

from pydantic import BaseModel

class LLMConfig(BaseModel):
    """ LLM config
    
    Args:
        provider(str): model provider
        base_url(str): llm base_url
        api_key(str): llm api key
        model(str): answer questions llm model name
    """

    provider: str
    base_url: str
    api_key: str
    model: str

class QDrantConfig(BaseModel):
    """ QDrant vector database config """

    host: str
    port: int

def load_llm_config() -> LLMConfig:
    """ load llm config in config.toml and make sure everything works well.
    Developers can set the enviroment virables in os to avoid leaking your api_key or something valuable.

    Returns:
        LLMConfig: user llm config
    """
    with open("../config.toml", "rb") as f:
        config:Dict[str, any] = tomllib.load(f)
        if 'llm' not in config.keys():
            raise KeyError("please make sure `llm` field is in config.toml.")
        
        llm_config = config["llm"]
        if not isinstance(llm_config, dict):
            raise TypeError("please make sure llm_config is a dict type.")
        
        provider = llm_config.get("provider", None) or os.environ.get("provider", None)
        base_url = llm_config.get("base_url", None) or os.environ.get("base_url", None)
        api_key = llm_config.get("api_key", None) or os.environ.get("api_key", None)
        model = llm_config.get("model", None) or os.environ.get("model", None)
        if not provider or not base_url or not api_key or not model:
            raise KeyError("please check config.toml and make sure llm have 4 parameters: `provider`, `base_url`, `api_key` and `model`. Please dont make them as an empty string.")
        
        print(f"User select {provider}'s model: {model}.")
        return LLMConfig(provider=provider, base_url=base_url, api_key=api_key, model=model)
    
def load_qdrant_config() -> QDrantConfig:
    """ load qdrant config from config.toml """
    
    with open("../config.toml", "rb") as f:
        config:Dict[str, any] = tomllib.load(f)
        if 'qdrant' not in config.keys():
            raise KeyError("please make sure `qdrant` field is in config.toml.")
        
        qdrant_config = config["qdrant"]
        if not isinstance(qdrant_config, dict):
            raise TypeError("please make sure qdrant_config is a dict type.")
        
        host = qdrant_config.get("host", None)
        port = qdrant_config.get("port", None)
        if not host or not port:
            raise KeyError("please make sure your `host` and `port` under [qdrant] both exist and their values are valid. Default `host`=`localhost` and `port`=6333.")

        return QDrantConfig(host=qdrant_config['host'])