from LLM import *
import yaml
from Utilities import *
from colorama import Back, Fore

prompt_template_provider = PromptTemplater("./prompts")
config_provider = ConfigProvider("./llm_configurations")

config = config_provider.get_config_from_menu()["llm"]

info = {"my name":"jakub brown", "my age":"38"}
    
llm = LLMwithKnowledge(
    model_name=config["model_name"], 
    knowledge=info,
    prompt_template=prompt_template_provider.get_prompt("rag"),
    url=config["url"],
    system_prompt=config["system_prompt"]
)

if __name__ == "__main__":
    while True:
        prompt = input(f"{Back.GREEN}(q)uit | print (m)essages | print (k)nowledge | (a) to knowledge | (r)eset knowledge{Back.RESET}  > ")
        if prompt == "q": break
        elif prompt == "m": llm.print_messages()
        elif prompt == "k": print(llm.knowledge)
        elif prompt == "a":
            key = input("knowledge title > ")
            info = input("additional knoweldge > ")
            llm.add_to_knowledge({key:info})
        elif prompt == "r":
            llm.reset_knowledge()
        else:
            llm.reset_memory()
            response = llm.answer_question(prompt)
            print(f"{Fore.YELLOW}{response}{Fore.RESET}")
            