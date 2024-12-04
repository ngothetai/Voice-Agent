from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, File, UploadFile, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import uvicorn
import json
from typing import Dict
import base64

from websockets import ConnectionClosed
from botvov.stt_service import STT_service
from botvov.llm_service import generate_response
from botvov.tts_service import TTS_service
from pydantic import BaseModel


class AudioBase64Request(BaseModel):
    base64_audio: str


class AudioBase64Response(BaseModel):
    response: str
    audio: str


def encode_audio_to_base64(file_bytes):
    encoded_string = base64.b64encode(file_bytes).decode('utf-8')
    return encoded_string

def decode_base64_to_audio(base64_string, output_file_path):
    audio_data = base64.b64decode(base64_string)
    with open(output_file_path, "wb") as audio_file:
        audio_file.write(audio_data)


def runner():
    app = FastAPI(
        title="VOV Assistant API",
        description="Voice interaction API with speech-to-text and text-to-speech capabilities",
        version="1.0.0",
        lifespan=None)
    # Configure CORS with default settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allows all origins
        allow_credentials=True,
        allow_methods=["*"],  # Allows all methods
        allow_headers=["*"],  # Allows all headers
    )

    # init home path
    @app.get('/')
    async def home():
        return {"message": "Welcome to VOV Assistant!"}

    # init chat api
    @app.websocket('/ws')
    async def websocket_endpoint(websocket: WebSocket):
        await websocket.accept()
        try:
            while True:
                audio_bytes = await websocket.receive_bytes()
                audio_base64 = encode_audio_to_base64(audio_bytes)
                message = STT_service(audio_base64)
                
                response, command = generate_response(message)
                if command:
                    await websocket.send_json({"command": command})
                audio_base64 = await TTS_service(response)
                audio_bytes = base64.b64decode(audio_base64)
                await websocket.send_bytes(audio_bytes)
                
        except (WebSocketDisconnect, ConnectionClosed):
            print("Client disconnected")
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