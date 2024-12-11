# llm_service.py

import logging
from typing import Tuple
import os
from typing import Dict, Iterable, List, Literal
from openai import OpenAI
import instructor
from pydantic import BaseModel, Field
import json


# Read configurations from environment variables
MODEL_NAME = os.getenv('MODEL_NAME', 'Qwen/Qwen2.5-3B-Instruct')
PROMPT_SYSTEM = os.getenv('PROMPT_SYSTEM', 'You are a helpful assistant. Please answer the following questions to the best of your ability proper Vietnamese.')
TEMPERATURE = float(os.getenv('TEMPERATURE', '0.5'))
ATTEMPTS = int(os.getenv('ATTEMPTS', '10'))

assistant = OpenAI(api_key="cant-be-empty", base_url="http://llm_serve:8000/v1/")
ask_assistant = instructor.from_openai(assistant)

# Get the list of channels by json file
channel_list = json.load(open("./botvov/chanels_vov.json", "r"))

class Channel(BaseModel):
    id: str = Field(..., pattern=r'^\d+$')
    name: str


def generate_response(
    query: str,
) -> Tuple[str, str | None]:
    mapping_id2name = dict()
    
    router_prompt = """
    <task>
    You are a helpful router for user queries.
    Given a user query, you may need some extra information for answering the query. So you need to select the best place to find the answer.
    You have the following options:
    1. If you can answer the query directly with your own knowledge, return "assistant".
    2. You will have the channels list with id and name for each. \
        If the query is directly related to requesting to open a certain channel in the provided list, return id of this channel. \
        If the requested channel is not available in the list, return "not available".
    </task>
    
    <available_channels>\n
    """
    
    router_prompt += str(channel_list)
    
    router_prompt += "\n</available_channels>"
    
    for it in channel_list.values():
        for channel in it:
            mapping_id2name[channel['id']] = channel['name']
    available_channels = list(mapping_id2name.keys())
    
    router_prompt += f"\n<query>\n{query}\n</query>"
    
    response = ask_assistant.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": router_prompt}],
        response_model=Literal["assistant", *available_channels, "not available"],
        max_retries=ATTEMPTS
    )
    
    if response == "assistant":
        # The assistant can answer the query directly -> give the direct query to llm again
        assistant_response = assistant.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": PROMPT_SYSTEM
                },
                {
                    "role": "user",
                    "content": "<available_channels>\n" + str(channel_list) + "\n</available_channels>\n" + query
                }
            ],
            temperature=TEMPERATURE
        ).choices[0].message.content
        return assistant_response, None
    else:
        # Add context to the query and ask llm again
        channel_id = response
        if channel_id in set(available_channels):
            context = f"Hệ thống đang bắt đầu mở kênh {mapping_id2name[channel_id]}."
        else:
            context = "Kênh người dùng yêu cầu không tồn tại trong danh sách các kênh có sẵn."
        query += "\n<additional_context>\n" + context + "\n</additional_context>\n"
        
        SUMMARY_RESPONSE = "You are an helpful assistant. You did do something and has result in context. Based on the query and context, give the user the final answer. If you need more information from the user, you can ask the user again to know more."
        assistant_response = assistant.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": SUMMARY_RESPONSE
                },
                {
                    "role": "user",
                    "content": query
                }
            ],
            temperature=TEMPERATURE
        ).choices[0].message.content
        return assistant_response, channel_id
