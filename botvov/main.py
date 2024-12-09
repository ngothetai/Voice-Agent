import functools
from fastapi import FastAPI, Response, File, UploadFile, APIRouter
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import base64
import asyncio
from botvov.stt_service import STT_service
from botvov.tts_service import TTS_service
from botvov.main_test import build_graph
from pydantic import BaseModel
from typing import Dict, Any

from burr.core import Application, ApplicationBuilder
from burr.tracking import LocalTrackingClient


def encode_audio_to_base64(file_bytes):
    encoded_string = base64.b64encode(file_bytes).decode('utf-8')
    return encoded_string


class BotVOVState(BaseModel):
    app_id: str
    query: str
    response: str
    command: Any
    
    @staticmethod
    def from_app(app: Application):
        state = app.state
        return BotVOVState(
            app_id=app.uid,
            query=state.get("query"),
            response=state.get("final_output"),
            command=state.get("command")
        )

@functools.lru_cache(maxsize=128)
def _get_applications(project_id: str, app_id: str=None) -> Application:
    graph = build_graph()
    tracker = LocalTrackingClient(project=project_id)
    if app_id is not None:
        builder = (
            ApplicationBuilder()
            .with_graph(graph)
            .with_tracker(tracker := LocalTrackingClient(project=project_id))
            .with_identifiers(app_id=app_id)
            .initialize_from(
                tracker,
                resume_at_next_action=True,
                default_state={"query": "Xin chào"},
                default_entrypoint="process_input",
            )
        )
    else:
        builder = (
            ApplicationBuilder()
            .with_graph(graph)
            .with_tracker(tracker := LocalTrackingClient(project=project_id))
            .with_identifiers()
            .initialize_from(
                tracker,
                resume_at_next_action=True,
                default_state={"query": "Xin chào", "command": None},
                default_entrypoint="process_input",
            )
        )
    return builder.build()

def _run_through(project_id: str, app_id: str, inputs: Dict[str, Any]) -> BotVOVState:  
    botvov_application = _get_applications(project_id, app_id)
    botvov_application.run(
        halt_after=["format_results"],
        inputs=inputs
    )
    return BotVOVState.from_app(botvov_application)


def runner():
    app = FastAPI(
        title="VOV Assistant API",
        description="Voice interaction API with speech-to-text and text-to-speech capabilities",
        version="1.0.0",
        lifespan=None
    )
    router = APIRouter()
    # Configure CORS with default settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allows all origins
        allow_credentials=True,
        allow_methods=["*"],  # Allows all methods
        allow_headers=["*"],  # Allows all headers
    )

    # @router.post("/create_new") # not use 
    # def create_new_application() -> str:
    #     app = _get_applications("1")
    #     return app.uid
    
    @router.post("/send_audio_query")
    def send_audio_query(audio: UploadFile = File(...)):
        audio_bytes = audio.file.read()
        audio_base64 = encode_audio_to_base64(audio_bytes)
        user_query = STT_service(audio_base64)
        response = _run_through(
            "1",
            "1",
            {
                "user_query": user_query
            }
        )
        
        return {
            "response": response.response,
            "command": response.command
        }

    @router.get("/get_audio_response")
    def get_audio_response():
        response = BotVOVState.from_app(_get_applications("1", "1"))
        # Call an async TTS function
        audio_base64 = asyncio.run(TTS_service(response.response))
        audio_response = base64.b64decode(audio_base64)
        
        return Response(content=audio_response, media_type="audio/wav", headers={
            "Content-Disposition": "inline; filename=response.wav"
        })

    app.include_router(router, prefix="/botvov", tags=["botvov-api"])

    # init home path
    @app.get('/')
    async def home():
        return {"message": "Welcome to VOV Assistant!"}

    
    return app
            

app = runner()

if __name__ == "__main__":
    uvicorn.run(
        "botvov.main:app",
        host="0.0.0.0",
        port=5000,
        ssl_keyfile="/app/work.duchungtech.com.key",
        ssl_certfile="/app/work.duchungtech.com.crt",
        reload=True
    )