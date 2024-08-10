import json
from pydantic import BaseModel


class Weather:
    function: dict = {
        'name': 'get_current_weather',
        'description': 'Lấy thông tin thời tiết hiện tại với vị trí được nhận',
        'parameters': {
            'type': 'object',
            'properties': {
                'location': {
                    'type': 'string',
                    'description':
                        'Thành phố và tiểu bang/ tỉnh thành, e.g. San Francisco, CA',
                },
                'unit': {
                    'type': 'string',
                    'enum': ['celsius', 'fahrenheit']
                },
            },
            'required': ['location'],
        },
    }

    def __init__(self):
        pass

    @staticmethod
    def get_current_weather(location: str, unit='fahrenheit'):
        """Get the current weather in a given location"""
        if 'tokyo' in location.lower():
            return json.dumps({
                'location': 'Tokyo',
                'temperature': '10',
                'unit': 'celsius'
            })
        elif 'san francisco' in location.lower():
            return json.dumps({
                'location': 'San Francisco',
                'temperature': '72',
                'unit': 'fahrenheit'
            })
        elif 'paris' in location.lower():
            return json.dumps({
                'location': 'Paris',
                'temperature': '22',
                'unit': 'celsius'
            })
        else:
            return json.dumps({
                'location': location,
                'temperature': f'Không có thông tin về thời tiết tại vị trí {location}'
            })
