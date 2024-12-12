import functools
import requests
import json
from typing import Dict, Any
import functools


class VOVChannelProvider:
    def __init__(self, url: str="https://adminmedia.kythuatvov.vn/api/channels?zarsrc=30&utm_source=zalo&utm_medium=zalo&utm_campaign=zalo&gidzl=ZIYZFoy_8M2FDAinBI4eRuysgZ0m9oTdn62gPM5m9Z2JPwjdPteYD9Llg6PbVYPYm6l_CJYH9RjcA3qgRG"):
        self._url = url
        self._channels = list()
        self._mapped_channel_list_and_id = dict()
        self._preprocess()
        
    def _preprocess(self):
        try:
            # response = requests.get(self._url)
            # response.raise_for_status()
            # xml_content = response.content.decode("utf-8")
            # channels = json.loads(xml_content)['data']['TV'] + json.loads(xml_content)['data']['Radio']['Tất cả kênh']
            
            # # Get only "id" and "name" from each dict element in res list using map
            # channels = list(map(lambda x: {"id": x["id"], "name": x["name"]}, channels))
            channels = json.loads(open("./botvov/channels_vov.json", "r").read())
            self._channels = channels
        except requests.exceptions.RequestException as e:
            raise Exception("Error while fetching data from VOV provider")
        
        for it in channels.values():
            for channel in it:
                self._mapped_channel_list_and_id[channel["id"]] = channel["name"]

    @functools.lru_cache(maxsize=128)
    def _get_channel_list(self) -> Dict[str, Any]:
        """
        Get the list of channel from VOV provider
        """
        return {
            "channels": self._channels
        }
    
    @functools.lru_cache(maxsize=128)
    def _open_channel(self, channel_id: str) -> Dict[str, Any]:
        """
        Open the channel with the given its id. User don't know about the channel id.
        User only know about channel name, so whenever they give any request about the channel it has nothing to do with the channel id.
        You must find the channel id from the channel name and open it by use _open_channel tool.
        """
        return {
            "action response": f"Radio is opening the channel: {self._mapped_channel_list_and_id[channel_id]}. Wait for a moment.",
            "data": {
                "type": "VOV",
                "message_id": channel_id,
                "message": self._mapped_channel_list_and_id[channel_id]
            }
        }


if __name__ == "__main__":
    vov_channel_provider = VOVChannelProvider()
    print(vov_channel_provider._get_channel_list())
    print(vov_channel_provider._open_channel("1"))