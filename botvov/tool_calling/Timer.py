import datetime
from typing import Any, Dict


class TimeProvider:
    """
    A class used to provide the current time.
    Methods
    -------
    _get_current_time() -> Dict[str, Any]:
        Returns the current time in the format "YYYY-MM-DD HH:MM:SS".
    """
    def __init__(self) -> None:
        pass
    
    def _get_current_time(self) -> Dict[str, Any]:
        """
        Get the current time from Time

        Returns:
            Dict[str, Any]: A dictionary containing the current time in the format "YYYY-MM-DD HH:MM:SS".
        """
        return {
            "tool response": "The current time"
        }
    
    def _show_time(self) -> Dict[str, Any]:
        """
        Show the current time.
        """
        return {
            "action response": "The current time was shown.",
            "data": {
                "type": "time",
                "message_id": None,
                "message": None
            }
        }