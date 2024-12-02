# llm_service.py

import os
from openai import OpenAI

# Read configurations from environment variables
MODEL_NAME = os.getenv('MODEL_NAME', 'Qwen/Qwen2.5-1.5B-Instruct')
PROMPT_SYSTEM = os.getenv('PROMPT_SYSTEM', 'You are a helpful assistant. Please answer the following questions to the best of your ability proper Vietnamese.')
TEMPERATURE = float(os.getenv('TEMPERATURE', '0.5'))

assistant = OpenAI(api_key="cant-be-empty", base_url="http://llm_serve:8000/v1/")

def generate_response(message: str):
    # Combine the system prompt with the user's message
    
    response = assistant.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": PROMPT_SYSTEM},
            {"role": "user", "content": message},
        ],
        temperature=TEMPERATURE
    )
    try:
        content = response.choices[0].message.content
    except:
        content = "Không có kết quả"
    return content