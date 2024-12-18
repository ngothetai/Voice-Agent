from pydantic import BaseModel, field_validator
from typing import Literal
from botvov.utils import read_channel_list


class ChannelResponse(BaseModel):
    # Schema channel_id must be in self._mapped_channel_list_and_id keys
    channel_id: str
    
    @field_validator("channel_id")
    @classmethod
    def check_channel_id(cls, value):
        _, mapped_channel_list_and_id = read_channel_list()
        if value not in mapped_channel_list_and_id.keys():
            raise ValueError(f"Channel id {value} not in the list of VOV channels")
        return value
    

class ResponseRouter(BaseModel):
    choice: Literal["channel_list", "broadcast_schedule", "current_time", "weather", "fallback"]
