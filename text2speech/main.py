from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from .text2speech import Text2Speech
from dotenv import load_dotenv
import json
import torch
import os
from types import SimpleNamespace
from fastapi import FastAPI, Request
import soundfile as sf
import io
import base64
from pydantic import BaseModel, Base64Str, ValidationError

class Speech(BaseModel):
    audio_base64_str : str


#===== function call =====
def TTS_service(text:str, text2speech, duration_net, generator):
    sampling_rate, output = text2speech.speak(text,duration_net,generator)
    # Convert the output to a bytes buffer
    buffer = io.BytesIO()
    sf.write(buffer, output, sampling_rate, format='WAV')
    buffer.seek(0)

    # Encode the buffer to base64
    audio_base64 = base64.b64encode(buffer.read()).decode('utf-8')
    return audio_base64
#======== end ===============


def runner():
    load_dotenv()
    #========fixed TTS===========
    config_file = os.environ['CONFIG_FILE']
    duration_model_path = os.environ['DURATION_MODEL'] 
    lightspeed_model_path = os.environ['LIGHTSPEED_MODEL_PATH']
    phone_set_file = os.environ['PHONE_SET_FILE']
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
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
    duration_net, generator = text2speech.load_models()
    
    app = FastAPI()

    @app.get('/')
    async def home():
        return {"message": "Welcome to Text2Speech Service!"}

    @app.post('/speak')
    async def speak(request: Request):
        data = await request.json()
        text = data['text']
        audio_base64 = TTS_service(
            text,
            text2speech=text2speech,
            duration_net=duration_net,
            generator=generator
        )
        try:
            item = Speech(audio_base64_str=audio_base64)
        except ValidationError as e:
            return JSONResponse(content=e.errors(), status_code=400)
        return JSONResponse(content=jsonable_encoder(item.model_dump()), status_code=200)

    return app

if __name__ == "__main__":
    app = runner()
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=6000)
