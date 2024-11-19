import functools
from burr.tracking import LocalTrackingClient
import importlib
import os
from typing import Any, Dict, List, Literal, Optional
import pydantic
from fastapi import APIRouter, FastAPI
from burr.core import Application, ApplicationBuilder
import application


app = FastAPI()
router = APIRouter()

class ConversationBOTVOV(pydantic.BaseModel):
    message: str
