import os, glob, yaml
from pathlib import Path
import tiktoken
from haystack.dataclasses import ChatMessage
from math import ceil
from simple_term_menu import TerminalMenu

class PromptTemplater:
    def __init__(self, folder):
        self._folder = folder
        
    def list_prompts(self):
        res = os.listdir(self._folder)
        return res
    
    def print_prompts(self):
        prompts = self.list_prompts()
        print("Following prompts are available in prompt library:")
        for p in prompts:
            print(p)
        
    def get_prompt(self, prompt_name):
        known_prompts = [Path(p) for p in self.list_prompts()]
        if prompt_name not in [p.stem for p in known_prompts]:
            ValueError(f"Prompt name `{prompt_name}` not found in prompt library.")
            
        file_name = [p for p in known_prompts if p.stem == prompt_name][0]
        with open(Path(self._folder) / file_name, "r") as f:
            prompt = f.read()
            
        return prompt
    
def count_tokens(string: str | list[str] | list[ChatMessage]) -> int:
    """Calculates the estimated number of tokens in a string.

    Args:
        string (str): String to be measured. Typically this will be a prompt or a sequence of prompts.

    Returns:
        int: Estimated number of tokens. Assumes 10% more tokens than returned by the tiktoken package.
    """
    if isinstance(string, str):
        string = [string]
    elif isinstance(string, ChatMessage):
        string = [string.content]
    elif string and isinstance(string, list) and all(isinstance(s, ChatMessage) for s in string):
        string = [c.content for c in string]
    elif string and isinstance(string, list) and all(isinstance(s, str) for s in string):
        pass
    else:
        raise ValueError("Input must be a single string, list of strings or list of ChatMessage objects.")
    
    string = "\n".join(string)
    
    encoding = tiktoken.get_encoding("cl100k_base")
    encoded_string = encoding.encode(string)
    num_tokens = len(encoding.encode(string))
    return ceil(num_tokens*1.1)

class ConfigProvider:
    def __init__(self, folder: str="./"):
        self.folder = Path(folder)
        
    def display_menu(self):
        configs = [str(a) for a in list(self.folder.glob("*.yml"))]
        
        if len(configs) == 1:
            return configs[0]
        
        terminal_menu = TerminalMenu(configs)
        i = terminal_menu.show()
        return configs[i]
    
    def get_config_from_menu(self):
        p = self.display_menu()
        with open(p, "r") as f:
            config = f.read()
        res = yaml.safe_load(config)
        return res