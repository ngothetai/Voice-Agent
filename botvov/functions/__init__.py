from botvov.utils.load_settings import load_settings
from typing import Dict
from qwen_agent.agents import Assistant

SETTINGS: Dict = load_settings("botvov/settings.yml")


def init_agent_service():
    llm_cfg = SETTINGS['llm']
    system = ("You are a helpful AI assistant which live in Viet Nam. Answer in proper Vietnamese.")

    tools = [
        'datetime_by_timezone',
        'weather'
    ]
    bot = Assistant(
        llm=llm_cfg,
        name='AI assistant',
        description='A helpful AI assistant can answer questions and perform tasks.',
        system_message=system,
        function_list=tools,
    )
    return bot
