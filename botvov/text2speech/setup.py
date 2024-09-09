import requests
import os
from tqdm import tqdm

models = [
    {
        'url': 'https://huggingface.co/spaces/ntt123/Vietnam-female-voice-TTS/resolve/main/duration_model.pth?download=true',
        'filename': 'duration_model.pth'
    },
        {
        'url': 'https://huggingface.co/spaces/ntt123/Vietnam-female-voice-TTS/resolve/main/gen_210k.pth?download=true',
        'filename': 'gen_210k.pth'
    },
        {
        'url': 'https://huggingface.co/spaces/ntt123/Vietnam-female-voice-TTS/resolve/main/gen_543k.pth?download=true',
        'filename': 'gen_543k.pth'
    },
        {
        'url': 'https://huggingface.co/spaces/ntt123/Vietnam-female-voice-TTS/resolve/main/gen_630k.pth?download=true',
        'filename': 'gen_630k.pth'
    },
    
]

save_model_directory = 'models'
os.makedirs(save_model_directory, exist_ok=True)

def download_model(url, filename,save_directory):
    local_path = os.path.join(save_directory, filename)
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        with open(local_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

for model in tqdm(models,desc='Download model .....'):
    download_model(model['url'], model['filename'],save_model_directory)



# download configs 

configs = [
    {
        'url': 'https://huggingface.co/spaces/ntt123/Vietnam-female-voice-TTS/resolve/main/config.json?download=true',
        'filename': 'config.json'
    },
        {
        'url': 'https://huggingface.co/spaces/ntt123/Vietnam-female-voice-TTS/resolve/main/phone_set.json?download=true',
        'filename': 'phone_set.json'
    }, 
]

save_config_directory = 'configs/text2speech'
os.makedirs(save_config_directory, exist_ok=True)
for config_name in tqdm(configs,desc='Download configs .....'):
    download_model(config_name['url'], config_name['filename'],save_config_directory)