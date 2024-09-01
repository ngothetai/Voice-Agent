from fastapi import FastAPI, Request
from qwen_agent.gui import WebUI
from botvov.assistant import QwenAssistant
import uvicorn
from fastapi.responses import JSONResponse, StreamingResponse
import httpx
import gradio as gr

def main():
    app = FastAPI()

    assistant = QwenAssistant()
    webUI = WebUI(assistant.assistant_instance())
    io = webUI.run(launch=False)
    gradio_app = gr.routes.App.create_app(io)

    @app.get('/')
    async def home():
        return {"message": "Welcome to VOV Assistant!"}

    @app.post('/api')
    async def chat(request: Request):
        data = await request.json()
        message = data.get('message')
        if not message:
            return JSONResponse(content={"error": "No message provided"}, status_code=400)

        response = assistant.chat(message)
        print(response)
        return JSONResponse(content={"response": response})
    app.mount("/demo", gradio_app)
    
    uvicorn.run(app, host='0.0.0.0', port=5000)

if __name__ == '__main__':
    main()