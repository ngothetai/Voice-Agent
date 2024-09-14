import asyncio
import io
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from websockets.exceptions import ConnectionClosed
from fastapi.websockets import WebSocketState
from qwen_agent.gui import WebUI
from botvov.assistant import QwenAssistant
import uvicorn
from fastapi.responses import JSONResponse, StreamingResponse
import httpx
import gradio as gr
import json
import base64
from openai import OpenAI


client = OpenAI(api_key="cant-be-empty", base_url="http://speech2text:9000/v1/")
def STT_service(audio_base64:str):
    global client
    buffer = io.BytesIO(base64.b64decode(audio_base64))
    buffer.seek(0)
    audio_file = buffer.read()
    transcript = client.audio.transcriptions.create(
        model="./models/PhoWhisper-small-ct2", file=audio_file, language="vi"
    )
    message = transcript.text
    return message


def main():
    app = FastAPI()

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

                assistant = QwenAssistant()
                response = assistant.chat(message)
                try:
                    content = response[-1]['content']
                except:
                    content = "Không có kết quả"

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
    
    
    @app.post('/chat')
    async def chat(request: Request):
        data = await request.json()
        message = data.get('message')
        if not message:
            return JSONResponse(content={"error": "No message provided"}, status_code=400)
        assistant = QwenAssistant()
        response = assistant.chat(message)
        return JSONResponse(content={"response": response})
    
    return app
app = main()

if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=5000)