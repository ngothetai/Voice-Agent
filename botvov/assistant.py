from qwen_agent.agents import Assistant, FnCallAgent


from botvov.commons.utils import load_file_config
from botvov.functions.weather import Weather
from botvov.functions.timer import Timer
from typing import Dict
import os


SETTINGS: Dict = load_file_config("configs/llm.yaml")


class QwenAssistant:
    def __init__(self):
        self.system = ("You are a helpful AI assistant. Answer shortly and clearly in proper Vietnamese and when referring to time, quantity write them all in words.")
        self.tools = [
            'datetime_by_timezone',
            'weather'
        ]
        self.assistant = FnCallAgent(
            llm=SETTINGS['llm'],
            description='A helpful AI assistant can answer questions and perform tasks.',
            system_message=self.system,
            function_list=self.tools,
        )
        self.messages = []

    def chat(self, query: str):
        self.messages.append({
            'role': 'user',
            'content': query,
        })
        response = []
        for response in self.assistant.run(self.messages):
            pass
        self.messages.extend(response)
        return response

    def assistant_instance(self):
        return self.assistant