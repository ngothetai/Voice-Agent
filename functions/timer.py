import json
from datetime import datetime
import pytz


class Timer:
    function: dict = {
        'name': 'get_current_time_by_timezone',
        'description': 'Lấy thời gian hiện tại theo múi giờ (timezone) được nhận',
        'parameters': {
            'type': 'object',
            'properties': {
                'timezone': {
                    'type': 'string',
                    'description':
                        'Thành phố và tiểu bang/ tỉnh thành, e.g. Asia/Tokyo',
                }
            },
            'required': ['timezone'],
        },
    }

    def __init__(self):
        pass

    @staticmethod
    def get_current_time_by_timezone(timezone_str):
        try:
            timezone = pytz.timezone(timezone_str)
            current_time = datetime.now(timezone)
            return current_time.strftime('%Y-%m-%d %H:%M:%S')
        except pytz.UnknownTimeZoneError:
            return f"Không có thông tin về múi giờ này: {timezone_str}"
