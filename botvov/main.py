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


def STT_service(audio_base64:str):
    client = OpenAI(api_key="cant-be-empty", base_url="http://speech2text:9000/v1/")
    buffer = io.BytesIO(base64.b64decode(audio_base64))
    buffer.seek(0)
    audio_file = buffer.read()
    transcript = client.audio.transcriptions.create(
        model="./models/PhoWhisper-small-ct2", file=audio_file, language="vi"
    )
    message = transcript.text
    return message


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
                
                    # Decode the base64 string to a bytes buffer
                    message = STT_service(audio_base64)
                    
                    await websocket.send_json({"transcript": message})
                else:
                    message = data['message']
                
                #@TODO: Must implement the chatbot logic here
                ##########################################
                response = assistant.completions.create(
                    model="meta-llama/Llama-3.2-1B",
                    prompt=message,
                    temperature=0.8
                )
                try:
                    content = response.choices[0].text
                except:
                    content = "Không có kết quả"
                ##########################################

                #================
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        "http://text2speech:6000/speak",
                        json={"text": content},
                        headers={"Content-Type": "application/json"}
                    )
                    response_data = response.json()
                    audio_base64 = response_data.get("audio_base64_str", "")

                # Send the base64 string to the front-end
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