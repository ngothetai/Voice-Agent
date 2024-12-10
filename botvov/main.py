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
from burr.core.persistence import SQLLitePersister
import uuid


def encode_audio_to_base64(file_bytes):
    encoded_string = base64.b64encode(file_bytes).decode('utf-8')
    return encoded_string

PROJECT_ID = "release_botvov_debug_tracking"


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
def _get_applications(app_id: str | None=None) -> Application:
    graph = build_graph()
    sqllite_persister =  SQLLitePersister(db_path="/app/botvov/.sqllite.db", table_name="burr_state", connect_kwargs={"check_same_thread": False})
    sqllite_persister.initialize()
    builder = (
        ApplicationBuilder()
        .with_graph(graph)
        .initialize_from(
            initializer=sqllite_persister,
            resume_at_next_action=True,
            default_state={"query": "Xin chào"},
            default_entrypoint="process_input",
        )
        .with_state_persister(sqllite_persister)
        .with_identifiers(app_id=app_id)
        .with_tracker("local", project=PROJECT_ID)
    )
    return builder.build()

def _run_through(app_id: str, inputs: Dict[str, Any]) -> BotVOVState:  
    botvov_application = _get_applications(app_id=app_id)
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

    @router.post("/create_new") # not use 
    def create_new_application() -> str:
        new_app = _get_applications(app_id=str(uuid.uuid4()))
        return new_app.uid
    
    @router.post("/send_audio_query")
    def send_audio_query(app_id: str, audio: UploadFile = File(...)):
        audio_bytes = audio.file.read()
        audio_base64 = encode_audio_to_base64(audio_bytes)
        user_query = STT_service(audio_base64)
        response = _run_through(
            app_id=app_id,
            inputs={
                "user_query": user_query
            }
        )
        
        return {
            "response": response.response,
            "command": response.command
        }

    @router.get("/get_audio_response")
    def get_audio_response(app_id: str):
        response = BotVOVState.from_app(_get_applications(app_id=app_id))
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