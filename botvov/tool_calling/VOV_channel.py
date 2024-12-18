import json
from typing import Dict, Any, List
import functools
from botvov.utils import _get_instructor_client, read_channel_list
from botvov.models import ChannelResponse
import os

MODEL_NAME = os.getenv('MODEL_NAME', 'Qwen/Qwen2.5-3B-Instruct')
PROMPT_SYSTEM = os.getenv('PROMPT_SYSTEM', 'You are a helpful assistant. Please answer the following questions to the best of your ability proper Vietnamese.')
TEMPERATURE = float(os.getenv('TEMPERATURE', '0.5'))
ATTEMPTS = int(os.getenv('ATTEMPTS', '10'))

class VOVChannelProvider:
    channel_list_url = "https://adminmedia.kythuatvov.vn/api/channels?zarsrc=30&utm_source=zalo&utm_medium=zalo&utm_campaign=zalo&gidzl=ZIYZFoy_8M2FDAinBI4eRuysgZ0m9oTdn62gPM5m9Z2JPwjdPteYD9Llg6PbVYPYm6l_CJYH9RjcA3qgRG"
    broadcast_schedule_url = "https://adminmedia.kythuatvov.vn/api/channels/broadcast-schedules/{channel_id}?from={start_date}&to={end_date}"
    
    def __init__(self):
        pass
    
    @classmethod
    def extract_channel_id(cls, user_query) -> ChannelResponse:
        channels, _ = read_channel_list()
        
        messages = [
                {
                    "role": "system",
                    "content": f"""
                    You are a professional radio operator, you are responsible for opening the radio channel for the audience to listen to.
                    Note: Any user quey which has mention with channel, so it always is the channel name because user never know about the channel id.
                    Use the information extracted from computer data and open the channel by channel id for the audience to listen to and provide response radio is opening channel by name.
                    Note: If in user query has open/ play channel command, you must provide the channel id and set open_channel to True. If not, you must provide the channel list and set open_channel to False.
                    <channel_list>
                        {json.dumps(channels)}
                    </channel_list>
                    """
                }
            ] + user_query

        res = _get_instructor_client().chat.completions.create(
            model=MODEL_NAME, 
            messages=messages,
            temperature=TEMPERATURE,
            top_p=0.8,
            response_model=ChannelResponse
        )
            
        return res

    @classmethod
    def _preprocess_broadcast_json(cls, response: Dict[str, Any]) -> List[Any] | None:
        data = response.get("data")
        if data:
            res = []
            for d in data.values():
                for item in d:
                    res.append({
                        "broadcast_date": item.get("broadcast_date"),
                        "name": item.get("name"),
                        "start_time": item.get("start_time"),
                        "end_time": item.get("end_time")
                    })
            return res
        else:
            return None
