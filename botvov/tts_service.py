import httpx

async def TTS_service(content: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://text2speech:6000/speak",
            json={"text": content},
            headers={"Content-Type": "application/json"}
        )
        response_data = response.json()
        audio_base64 = response_data.get("audio_base64_str", "")
    return audio_base64
