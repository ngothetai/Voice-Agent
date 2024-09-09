from fastapi import FastAPI, Request
from qwen_agent.gui import WebUI
from botvov.assistant import QwenAssistant
import uvicorn
from fastapi.responses import JSONResponse, StreamingResponse
import httpx
import gradio as gr
import torch
import json, os
from types import SimpleNamespace
import soundfile as sf

from botvov.text2speech import Text2Speech
from dotenv import load_dotenv

load_dotenv()
#========fixed TTS===========
config_file = os.environ['CONFIG_FILE']
duration_model_path = os.environ['DURATION_MODEL'] 
lightspeed_model_path = os.environ['LIGHTSPEED_MODEL_PATH']
phone_set_file = os.environ['PHONE_SET_FILE']
device = "cuda" if torch.cuda.is_available() else "cpu"
# Load configuration and phone set

with open(config_file, "r") as f:
    hps = json.load(f, object_hook=lambda x: SimpleNamespace(**x))
    f.close()
with open(phone_set_file, "r") as f:
    phone_set = json.load(f)
    f.close()

assert phone_set[0][1:-1] == "SEP"
assert "sil" in phone_set
sil_idx = phone_set.index("sil")

text2speech = Text2Speech(
    hps=hps,
    phone_set=phone_set,
    sil_idx=sil_idx,
    config_file=config_file,
    duration_model_path=duration_model_path,
    lightspeed_model_path=lightspeed_model_path,
    phone_set_file=phone_set_file,
    device=device,
)
#===== function call =====
def TTS_service(text:str):
    sampling_rate, output = text2speech.speak(text)
    return sampling_rate,output
#======== end ===============


def main():
    app = FastAPI()

    assistant = QwenAssistant()
    webUI = WebUI(assistant.assistant_instance())
    io = webUI.run(launch=False)

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
        try:
            content= response[-1]['content']
        except:
            content = "Không có kết quả"
        print(response)
        #================
        sampling_rate, output = TTS_service(content)
        output_dir = 'outputs'
        os.makedirs(output_dir, exist_ok=True)
        file_path = f"./{output_dir}/nghiaamthanh.wav"
        
        sf.write(file_path, output, sampling_rate)
        #==============
        return JSONResponse(content={"response": response})
    app = gr.mount_gradio_app(app, io, path="/demo")
    
    uvicorn.run(app, host='0.0.0.0', port=5000)

if __name__ == '__main__':
    main()