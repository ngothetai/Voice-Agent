# llm_service.py

import os
from typing import Dict, Iterable, List, Literal
from openai import OpenAI
import instructor
from pydantic import BaseModel, Field
import json


# Read configurations from environment variables
MODEL_NAME = os.getenv('MODEL_NAME', 'Qwen/Qwen2.5-1.5B-Instruct')
PROMPT_SYSTEM = os.getenv('PROMPT_SYSTEM', 'You are a helpful assistant. Please answer the following questions to the best of your ability proper Vietnamese.')
TEMPERATURE = float(os.getenv('TEMPERATURE', '0.5'))
ATTEMPTS = int(os.getenv('ATTEMPTS', '10'))

assistant = OpenAI(api_key="cant-be-empty", base_url="http://llm_serve:8000/v1/")
# ask_assistant = instructor.from_openai(assistant)

# Get the list of channels by json file
# channel_list = json.load(open("./chanels_vov.json", "r"))

class Channel(BaseModel):
    id: str = Field(..., pattern=r'^\d+$')
    name: str


def router(
    channels: Dict[str, Iterable[Channel]],
    query: str,
    chat_history: List[Dict[str, str]] | None = None,
):
    router_prompt = """
    <task>
    You are a helpful router for user queries.
    Given a user query, you may need some extra information for answering the query. So you need to select the best place to find the answer.
    You have the following options:
    1. If you can answer the query directly with your own knowledge, return "assistant".
    2. You will have the channels list with id and name for each. If the query is directly related to requesting to open a certain channel in the provided list, return the channel id.
    </task>
    
    <available_channels>
    """
    
    for it in channels.values():
        for channel in it:
            router_prompt += f"\n{channel.id}. {channel.name}"
    
    router_prompt += "\n</available_channels>"
    id_available = [channel.id for it in channels.values() for channel in it]
    
    if chat_history:
        router_prompt += "\n<chat_history>"
        for chat in chat_history:
            router_prompt += f"\n{chat['role']}: {chat['content']}"
        router_prompt += "\n</chat_history>"
    
    router_prompt += f"\n<query>\n{query}\n</query>"
    
    response = ask_assistant.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "system", "content": router_prompt}],
        response_model=Literal[*id_available, 'assistant'],
        max_retries=ATTEMPTS
    )
    print("=== response===", response)
    

def generate_response(messages: str):
    # Combine the system prompt with the user's message
    
    response = assistant.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "system", "content": PROMPT_SYSTEM}, {"role": "user", "content": messages}],
        temperature=TEMPERATURE
    )
    try:
        content = response.choices[0].message.content
    except:
        content = "Không có kết quả"
    return content