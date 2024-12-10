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

    class CreateApplicationResponse(BaseModel):
        uid: str

    @router.post("/create_new", response_model=CreateApplicationResponse, summary="Create new app for new user", description="Register new user_id for new client to user later") # not use 
    def create_new_application():
        new_app = _get_applications(app_id=str(uuid.uuid4()))
        response = CreateApplicationResponse(uid=new_app.uid)
        return response.model_dump()

    class CommandResponse(BaseModel):
        type: str
        message_id: str
        message: str

    class AudioQueryResponse(BaseModel):
        status_code: int
        text_response: str
        data: CommandResponse | None
        message: str
        status: bool

    @router.post("/send_audio_query", response_model=AudioQueryResponse, summary="Send an audio query", description="Processes an audio query and returns the response.")
    def send_audio_query(app_id: str, audio: UploadFile = File(...)):
        """
        Processes an audio query and returns the response.

        - **app_id**: The application ID
        - **audio**: The audio file to be processed
        """
        try:
            audio_bytes = audio.file.read()
        except Exception as e:
            return {
                "status_code": 400,
                "text_response": "",
                "data": None,
                "message": "Invalid file type error",
                "status": False
            }
        
        audio_base64 = encode_audio_to_base64(audio_bytes)
        
        try:
            user_query = STT_service(audio_base64)
        except Exception as e:
            return {
                "status_code": 423,
                "text_response": "",
                "data": None,
                "message": "Error recognition audio",
                "status": False
            }
            
        try:
            response = _run_through(
                app_id=app_id,
                inputs={
                    "user_query": user_query
                }
            )
        except Exception as e:
            return {
                "status_code": 422,
                "text_response": "",
                "data": None,
                "message": "No response AI",
                "status": False
            }
    
        return {
            "status_code": 200,
            "text_response": response.response,
            "data": response.command,
            "message": "Response successful",
            "status": True
        }


    @router.get("/get_audio_response")
    def get_audio_response(app_id: str):
        response = BotVOVState.from_app(_get_applications(app_id=app_id))
        # Call an async TTS function
        try:
            audio_base64 = asyncio.run(TTS_service(response.response))
        except Exception as e:
            return {
                "status_code": 424,
                "text_response": "",
                "message": "Error speech text",
                "status": False
            }
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