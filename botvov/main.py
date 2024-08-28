from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from botvov.assistant import QwenAssistant
import uvicorn

app = FastAPI()
assistant = QwenAssistant()

@app.post('/chat')
async def chat(request: Request):
    data = await request.json()
    message = data.get('message')
    if not message:
        return JSONResponse(content={"error": "No message provided"}, status_code=400)

    response = assistant.chat(message)
    print(response)
    return JSONResponse(content={"response": response})

if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=5000)