import io

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from websockets.exceptions import ConnectionClosed
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from fastapi.responses import JSONResponse
import httpx
import json
import base64
from openai import OpenAI
import logging
from botvov.stt_service import STT_service
from botvov.llm_service import generate_response
from botvov.tts_service import TTS_service


def runner():
    app = FastAPI()
    assistant = OpenAI(api_key="cant-be-empty", base_url="http://llm_serve:8000/v1/")
    
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

    #=====================================================================================
    # init chat api
    @app.websocket('/api')
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