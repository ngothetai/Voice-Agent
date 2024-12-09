from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, File, UploadFile, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import uvicorn
import json
from typing import Dict
import base64
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
        version="1.0.0",)
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
                data = await websocket.receive_text()
                data = json.loads(data)
                
                data_type = data['type']
                if data_type == 'audio':
                    audio_base64 = data['audio']
                    message = STT_service(audio_base64)
                    await websocket.send_json({"transcript": message})
                else:
                    message = data['message']
                
                content = generate_response(message)
                audio_base64 = await TTS_service(content)
                await websocket.send_json({"response": content, "audio": audio_base64})
                
        except (WebSocketDisconnect, ConnectionClosed):
            print("Client disconnected")

    # init post api
    @app.post('/file_audio',
              summary="Process Audio File",
              description="Accepts an audio file, processes it for STT and TTS, and returns the generated audio response.",
              response_class=FileResponse,
              responses={
                200: {
                    "description": "Successful Response",
                    "content": {
                        "audio/wav": {
                            "example": "output_audio_file.wav"
                        }
                    }
                }
              }
    )
    async def post_file_audio_endpoint(file: UploadFile = File(..., description="Audio file in WAV format", example="audio_file.wav")):
        base64_audio = encode_audio_to_base64(await file.read())
        message = STT_service(base64_audio)
        content = generate_response(message)
        base64_audio = await TTS_service(content)
        output_file_path = "output_audio_file.wav"
        decode_base64_to_audio(base64_audio, output_file_path)
        return FileResponse(output_file_path, media_type='audio/wav', filename='output_audio_file.wav')

    @app.post('/base64_audio',
                summary="Process Base64 Audio",
                description="Accepts audio in Base64 format, processes it for STT and TTS, and returns the response and generated audio as Base64.",
                response_model=AudioBase64Response,
                responses={
                    200: {
                        "description": "Successful Response",
                        "content": {
                            "application/json": {
                                "example": {
                                    "response": "Xin chào! Ngày hôm nay của bạn thế nào?",
                                    "audio": "base64_string"
                                }
                            }
                        }
                    }
                }
    )
    async def post_base64_audio_endpoint(request: AudioBase64Request = Body(..., example={"base64_audio": "base64_string"})):
        base64_audio = request.base64_audio
        message = STT_service(base64_audio)
        content = generate_response(message)
        base64_audio = await TTS_service(content)
        return {"response": content, "audio": base64_audio}

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