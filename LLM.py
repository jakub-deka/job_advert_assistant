from email import message
from haystack_integrations.components.generators.ollama import OllamaChatGenerator
from haystack.components.generators.chat import OpenAIChatGenerator
from typing import Any
from haystack.dataclasses import ChatMessage, ChatRole
from colorama import Fore
from haystack.components.builders import PromptBuilder
from Utilities import *
import json
from haystack.utils import Secret
from pathlib import Path


class LLM:
    def __init__(
        self,
        model_name: str,
        url: str | None = None,
        system_prompt: str = "",
        return_json: bool = False,
        prompt_template: str = "",
        log_file_path: str | None = None,
        messages: list[ChatMessage] | None = None,
    ):
        if len(model_name.split("/")) < 2:
            raise ValueError(
                f"Provided embed model is incorrect. Format accepted is `provider/modelname`. E.g. `ollama/snowlake-arctic-embed:137m` or `openai/text-embedding-ada-002`."
            )
        self.__provider = model_name.split("/")[0]
        self.__model_name = "/".join(model_name.split("/")[1:])
        self.__url = url
        self.__system_prompt = system_prompt

        self.__prompt_template = prompt_template
        self.__prompt_builder = PromptBuilder(template=self.__prompt_template)

        if messages is None:
            self.__messages = []
        else:
            self.__messages = messages

        self.__generation_kwargs = None

        self.log_file_path = log_file_path
        if self.log_file_path is not None:
            self.log_file_path = Path(self.log_file_path)
            self.log_file_path.unlink(missing_ok=True)
            self.log_file_path.touch()
            self.append_message_to_log_file("SYSTEM", system_prompt)

        if self.__provider == "ollama":
            if return_json:
                self.__generation_kwargs = {"format": "json", "temperature": 0}

            self.__generator = OllamaChatGenerator(
                model=self.__model_name,
                url=self.__url,
                generation_kwargs=self.__generation_kwargs,
            )
            self.__messages.append(ChatMessage.from_system(self.__system_prompt))
        elif self.__provider == "openai":
            if return_json:
                self.__generation_kwargs = {
                    "response_format": {"type": "json_object"},
                    "temperature": 0,
                }

            self.__generator = OpenAIChatGenerator(
                model=self.__model_name,
                generation_kwargs=self.__generation_kwargs,
                # api_base_url = self.__url
            )
            self.__messages.append(ChatMessage.from_system(self.__system_prompt))
        elif self.__provider == "openrouter":
            if return_json:
                self.__generation_kwargs = {
                    "response_format": {"type": "json_object"},
                    "temperature": 0,
                }

            self.__generator = OpenAIChatGenerator(
                model=self.__model_name,
                generation_kwargs=self.__generation_kwargs,
                api_base_url=self.__url,
                api_key=Secret.from_env_var("OPENROUTER_API_KEY"),
            )
            self.__messages.append(ChatMessage.from_system(self.__system_prompt))

    def append_message_to_log_file(self, author: str, message: str):
        if self.log_file_path is not None:
            with open(self.log_file_path, "a") as f:
                f.write(author)
                f.write("\n------------\n")
                f.write(message)
                f.write("\n------------\n")

    def reset_memory(self, system_prompt: str | None = None):
        self.__messages = []
        if system_prompt is not None:
            self.__system_prompt = system_prompt
        self.__messages.append(ChatMessage.from_system(self.__system_prompt))

    def generate(self, **kwargs):
        if "plain_message" in kwargs.keys():
            prompt = kwargs.pop("plain_message")
        elif "prompt_template" in kwargs.keys():
            prompt_template = kwargs.pop("prompt_template")
            prompt = PromptBuilder(template=prompt_template).run(**kwargs)["prompt"]
        else:
            prompt = self.__prompt_builder.run(**kwargs)["prompt"]

        self.__messages.append(ChatMessage.from_user(prompt))
        number_of_tokens = count_tokens(self.__messages)

        response = self.__generator.run(self.__messages)["replies"][0]
        self.__messages.append(
            ChatMessage.from_assistant(response.content, response.meta)
        )

        self.append_message_to_log_file("USER", prompt)
        self.append_message_to_log_file("ASSISTANT", response.content)
        res = {
            "response": response.content,
            "prompt": prompt,
            "prompt_token_count": number_of_tokens,
            "response_token_count": count_tokens(response.content),
        }
        return res

    # region PROPERTIES
    @property
    def prompt_template(self):
        return self.__prompt_template

    @prompt_template.setter
    def prompt_template(self, value):
        self.__prompt_template = value
        self.__prompt_builder = PromptBuilder(template=self.__prompt_template)

    @property
    def model_name(self):
        return f"{self.__provider}/{self.__model_name}"

    @property
    def url(self):
        return self.__url

    @property
    def generation_kwargs(self):
        return self.__generation_kwargs

    @property
    def messages(self):
        return self.__messages

    # endregion

    def print_messages(self):
        for m in self.messages:
            print(m.role)
            print(m.content)

    def get_last_message(self, role: ChatRole | None = None):
        if role is None:
            filtered_messages = [m for m in self.messages][::-1]
        else:
            filtered_messages = [m for m in self.messages if m.role == role][::-1]
        if len(filtered_messages) > 0:
            res = filtered_messages[0]
        else:
            # Return empty message
            res = ChatMessage(content="<nothing here yet>", role=role, name=None)

        return res


class LLMwithKnowledge(LLM):
    def __init__(
        self,
        model_name: str,
        knowledge: list[dict[str:str]],
        prompt_template: str,
        url: str | None = None,
        system_prompt: str = "",
        return_json: bool = False,
        log_file_path: str | None = None,
        messages: list[ChatMessage] | None = None,
    ):
        super().__init__(
            model_name,
            url,
            system_prompt,
            return_json,
            prompt_template,
            log_file_path,
            messages,
        )
        self.knowledge = knowledge
        self._prompt_builder = PromptBuilder(
            self.prompt_template, required_variables=["context", "question"]
        )

    def add_to_knowledge(self, information: dict[str:str]):
        self.knowledge = {**self.knowledge, **information}

    def reset_knowledge(self):
        self.knowledge = {}

    def answer_question(self, question: str, **kwargs):
        """Returns the response from the LLM using knowledge provided.

        Args:
            question (str): _description_
        """
        prompt = self._prompt_builder.run(
            context=self.knowledge, question=question, **kwargs
        )["prompt"]
        reply = self.generate(plain_message=prompt)

        return reply
