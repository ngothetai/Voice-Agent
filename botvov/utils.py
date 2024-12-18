from typing import List, Tuple, Any, Dict
import json
import requests
from openai import OpenAI
import functools
import base64
import instructor


@functools.lru_cache
def _get_llm_client():
    assistant = OpenAI(
        api_key="cant-be-empty",
        base_url="http://llm_serve:8000/v1",
    )
    return assistant


@functools.lru_cache
def _get_instructor_client():
    assistant = _get_llm_client()
    return instructor.from_openai(assistant)


def encode_audio_to_base64(file_bytes: bytes) -> str:
    encoded_string = base64.b64encode(file_bytes).decode('utf-8')
    return encoded_string


def user_query_format(user_query: str):
    return {
        "role": "user",
        "content": user_query
    }
    
def assistant_response_format(assistant_response: str):
    return {
        "role": "assistant",
        "content": assistant_response
    }
    

def read_channel_list() -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
        mapped_channel_list_and_id = dict()
        try:
            channels = json.loads(open("./botvov/channels_vov.json", "r").read())
        except requests.exceptions.RequestException as e:
            raise Exception("Error while fetching data from VOV provider")
        
        for it in channels.values():
            for channel in it:
                mapped_channel_list_and_id[channel["id"]] = channel["name"]
        return channels, mapped_channel_list_and_id
    

REPLACE_DICT = {
    "%": " phần trăm",
    "°C": " độ C",
    "°F": " độ F",
    "km/h": " km mỗi giờ",
    "m/s": " mét mỗi giây",
    " mm": " mi li mét",
    " cm": " xăng ti mét",
    " m ": " mét ",
    " km": " ki lô mét",
    "Celcius": "C",
    "Fahrenheit": "F",
    "Celsius": "C",
    "Farenheit": "F",
}


def replace_words(text: str, replace_dict: Dict[str, str]= REPLACE_DICT) -> str:
    for k, v in replace_dict.items():
        text = text.replace(k, v)
    return text