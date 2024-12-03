import io
import base64
from openai import OpenAI

def STT_service(audio_base64: str):
    client = OpenAI(api_key="cant-be-empty", base_url="http://speech2text:9000/v1/")
    buffer = io.BytesIO(base64.b64decode(audio_base64))
    buffer.seek(0)
    audio_file = buffer.read()
    transcript = client.audio.transcriptions.create(
        model="./models/PhoWhisper-small-ct2", file=audio_file, language="vi"
    )
    message = transcript.text
    return message
