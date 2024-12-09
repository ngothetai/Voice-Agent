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

def decode_base64_to_audio(base64_string, output_file_path):
    audio_data = base64.b64decode(base64_string)
    with open(output_file_path, "wb") as audio_file:
        audio_file.write(audio_data)


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
            # .with_entrypoint("process_input")
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
                default_state={"query": "Xin chào"},
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

    @router.post("/create_new")
    def create_new_application(project_id: str) -> str:
        app = _get_applications(project_id)
        return app.uid
    
    @router.post("/get_audio_response/{project_id}/{app_id}")
    def send_audio_query(project_id: str, app_id: str, audio: UploadFile = File(...)):
        audio_bytes = audio.file.read()
        audio_base64 = encode_audio_to_base64(audio_bytes)
        user_query = STT_service(audio_base64)
        response = _run_through(
            project_id,
            app_id,
            {
                "user_query": user_query
            }
        )
        
        # Call an async TTS funtion
        audio_response = asyncio.run(TTS_service(response.response))
        return Response(content=audio_response, media_type="audio/wav")
        
    
    @router.post("/get_command/{project_id}/{app_id}")
    def get_command(project_id: str, app_id: str):
        response = BotVOVState.from_app(_get_applications(project_id, app_id))

        return {
            "response": response.response,
            "command": response.command
        }

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