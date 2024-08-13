import json
from qwen_agent.tools.base import BaseTool, register_tool
from typing import Dict, List, Optional


@register_tool('weather')
class Weather(BaseTool):
    description = "Lấy thông tin thời tiết hiện tại với vị trí được nhận"
    parameters: List[Dict] = [{
        'name': 'vị trí',
        'type': 'string',
        'description': 'Thành phố và tiểu bang/ tỉnh thành, e.g. San Francisco, CA',
        'required': True
    }]

    def __init__(self, cfg: Optional[Dict] = None):
        super().__init__(cfg)

    def call(self, params: str, **kwargs) -> str:
        location = json.loads(params)['location']
        """Get the current weather in a given location"""
        if 'tokyo' in location.lower():
            return json.dumps({
                'vị trí': 'Tokyo',
                'nhiệt độ': '10',
                'đơn vị': 'celsius'
            })
        elif 'san francisco' in location.lower():
            return json.dumps({
                'vị trí': 'San Francisco',
                'nhiệt độ': '72',
                'đơn vị': 'fahrenheit'
            })
        elif 'paris' in location.lower():
            return json.dumps({
                'vị trí': 'Paris',
                'nhiệt độ': '22',
                'đơn vị': 'celsius'
            })
        else:
            return json.dumps({
                'vị trí': location,
                'nhiệt độ': f'Không có thông tin về thời tiết tại vị trí {location}'
            })
