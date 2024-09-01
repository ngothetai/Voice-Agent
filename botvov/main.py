from fastapi import FastAPI, Request
from qwen_agent.gui import WebUI
from botvov.assistant import QwenAssistant
import uvicorn
from fastapi.responses import JSONResponse, StreamingResponse
import httpx

def main():
    assistant = QwenAssistant()
    # Create a chat app by API
    app = FastAPI()
    webUI = WebUI(assistant.assistant_instance())
    webUI.run(server_name="0.0.0.0", server_port=5000)
    
    # @app.get('/')
    # async def index():
    #     return {"message": "Hello, World"}

    # @app.post('/chat')
    # async def chat(request: Request):
    #     data = await request.json()
    #     message = data.get('message')
    #     if not message:
    #         return JSONResponse(content={"error": "No message provided"}, status_code=400)

    #     response = assistant.chat(message)
    #     print(response)
    #     return JSONResponse(content={"response": response})

    # @app.get('/webui/{path:path}')
    # async def webui(request: Request, path: str):
    #     async with httpx.AsyncClient() as client:
    #         url = f"http://0.0.0.0:5001/{path}"
    #         response = await client.get(url, params=request.query_params, headers=request.headers)
    #         return StreamingResponse(response.aiter_raw(), status_code=response.status_code, headers=response.headers)

    # uvicorn.run(app, host='0.0.0.0', port=5000)
        

if __name__ == '__main__':
    # # Define the argument parser
    # parser = argparse.ArgumentParser(description="Run the chatbot application.")
    # parser.add_argument('--type', type=str, default='api', help='Type of run: api or webui')

    # # Parse the arguments
    # args = parser.parse_args()
    # print("hiih", args.type)

    # Call the main function with the parsed arguments
    main()
