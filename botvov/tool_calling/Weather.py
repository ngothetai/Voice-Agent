from typing import Any, Dict
import requests
import json
import functools
from openai import OpenAI
import os

MODEL_NAME = os.getenv('MODEL_NAME', 'Qwen/Qwen2.5-3B-Instruct')
@functools.lru_cache
def _get_llm_client():
    assistant = OpenAI(
        api_key="cant-be-empty",
        base_url="http://llm_serve:8000/v1",
    )
    return assistant


class WeatherProvider:
    def __init__(self) -> None:
        self.__API_key = "ce27d930ccb4ad4d2168b6d38dc6de60"
        self._open_weather_url = "https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={API_key}&lang=vi&units=metric"
        
    def _summary_weather(self, weather: Dict[str, Any]) -> str:
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
        )
        
        # Re-write the response
        res = ai.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional content editor, use a paragraph and rewrite it in a more professional and shorten way, and make sure all words are in Vietnamese."
                },
                {
                    "role": "user",
                    "content": str(res.choices[0].message.content)
                }
            ],
        )
            
        return res.choices[0].message.content
    
    def _query_weather(self, lat:str, long:str) -> Dict[str, Any]:
        """
        Get the weather information now a day
        """
        lat = str(round(float(lat), 2))
        long = str(round(float(long), 2))
        self._response = requests.get(self._open_weather_url.format(lat=lat, lon=long, API_key=self.__API_key))
        if self._response.status_code == 200:
            return {
                "weather": self._summary_weather(self._response.json())
            }
        else:
            return {
                "error": "Cannot fetch the weather data"
            }
            
    def _show_weather(self) -> Dict[str, Any]:
        """
        Send the weather information for user know
        """
        return {
            "action response": "The weather information was shown.",
            "data": {
                "type": "weather",
                "message_id": None,
                "message": self._response.json()
            }
        }