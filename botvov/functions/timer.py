import json
from datetime import datetime
import pytz
from qwen_agent.tools.base import BaseTool, register_tool
from typing import Dict, Optional


@register_tool('datetime_by_timezone')
class Timer(BaseTool):
    description = ("từ thông tin múi giờ (timezone) được nhận (Nếu người dùng không cung cấp thông tin về múi giờ, "
                   "không gọi bất kì hàm nào mà hãy yêu cầu người dùng cung cấp thêm thông tin này), "
                   "sau đó hãy chuyển về dạng string múi giờ chuẩn quốc tế, "
                   "cuối cùng đưa ra thời gian (giờ) và ngày hiện tại theo múi giờ đó.")
    parameters = [{
        'name': 'múi giờ',
        'type': 'string',
        'description': 'Tên cụ thể của Châu lục/ Thành phố, ví dụ như Asia/Tokyo',
        'required': True
    }]

    def __init__(self, cfg: Optional[Dict] = None):
        super().__init__(cfg)

    def call(self, params: str, **kwargs) -> str:
        timezone_str = json.loads(params)['múi giờ']
        try:
            timezone = pytz.timezone(timezone_str)
            current_time = datetime.now(timezone)
            current_time = current_time.strftime('%Y-%m-%d %H:%M:%S')
            return json.dumps({
                'múi giờ': f'{timezone_str}',
                'thời gian hiện tại': current_time
            })
        except pytz.UnknownTimeZoneError:
            return f"Không có thông tin về múi giờ này: {timezone_str}"
