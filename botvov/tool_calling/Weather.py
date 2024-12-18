from typing import Any, Dict
import requests
import json
import os
from botvov.utils import _get_llm_client

MODEL_NAME = os.getenv('MODEL_NAME', 'Qwen/Qwen2.5-3B-Instruct')
TEMPERATURE = float(os.getenv('TEMPERATURE', '0.5'))


class WeatherProvider:
    API_key = "ce27d930ccb4ad4d2168b6d38dc6de60"
    open_weather_url = "https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={API_key}&lang=vi&units=metric"
    
    def __init__(self) -> None:
        pass    

    @classmethod
    def _summary_weather(cls, weather: Dict[str, Any]) -> str | None:
        ai = _get_llm_client()
        res = ai.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": """
                    You are a professional weather editor, use the information extracted from computer data and summarize it into a paragraph with all words in Vietnamese.
                    Then you will read it on live TV for the audience to understand the weather information so your paragraph must be clear, concise and easy understand.
                    """
                },
                {
                    "role": "user",
                    "content": json.dumps(weather)
                }
            ],
            temperature=0.2,
        )
        
        # Re-write the response
        # res = ai.chat.completions.create(
        #     model=MODEL_NAME,
        #     messages=[
        #         {
        #             "role": "system",
        #             "content": "You are a professional content editor, use a paragraph and rewrite it in a more professional and shorten way, and make sure all words are in Vietnamese."
        #         },
        #         {
        #             "role": "user",
        #             "content": str(res.choices[0].message.content)
        #         }
        #     ],
        #     temperature=TEMPERATURE,
        # )
            
        return res.choices[0].message.content