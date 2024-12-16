from typing import Any, Dict, List
import datetime
import requests


class VOVChannelBroadcastSchedule:
    def __init__(self) -> None:
        self._url = "https://adminmedia.kythuatvov.vn/api/channels/broadcast-schedules/1?from={start_date}&to={end_date}"
    
    def _preprocess_broadcast_json(self, response: Dict[str, Any]) -> List[Any] | None:
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
        
    
    def _get_broadcast_schedule(self) -> Dict[str, Any]:
        # Fetch the broadcast schedule from start_date to end_date
        
        date = datetime.datetime.now().strftime("%d-%m-%Y")
        #@TODO: implement the extract date from the user query

        self._response = requests.get(self._url.format(start_date=date, end_date=date))
        if self._response.status_code == 200:
            res = self._preprocess_broadcast_json(self._response.json())
            if res:
                return {
                    "broadcast_schedule": res
                }
            else:
                return {
                    "broadcast_schedule": f"Cannot fetch the broadcast schedule in {date}"
                }
        else:
            return {
                "broadcast_schedule": f"Cannot fetch the broadcast schedule in {date}"
            }
    
    def _show_broadcast_schedule(self) -> Dict[str, Any]:
        """
        Show the broadcast schedule.
        """
        return {
            "action response": "The broadcast schedule was shown. You don't need answer all of schedule, just answer the overaw information. Example: 'Today, there are 20 programs will be broadcasted. The detail was shown on the screen.'",
            "data": {
                "type": "broadcast_schedule",
                "message_id": "1",
                "message": self._response.json()['data']
            }
        }
