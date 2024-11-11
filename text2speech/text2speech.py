import json
import torch
import numpy as np
import re as regex
import unicodedata
from types import SimpleNamespace
from .models import DurationNet, SynthesizerTrn
import soundfile as sf



class Text2Speech:
    def __init__(self, hps,sil_idx,phone_set,config_file, duration_model_path, lightspeed_model_path, phone_set_file, device):
        self.hps = hps
        self.sil_idx = sil_idx
        self.phone_set = phone_set
        self.config_file = config_file
        self.duration_model_path = duration_model_path
        self.lightspeed_model_path = lightspeed_model_path
        self.phone_set_file = phone_set_file
        self.device = device
        
        # Initialize attributes
        self.space_re = regex.compile(r"\s+")
        self.number_re = regex.compile(r"([0-9]+)")
        self.digits = ["không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín"]
        self.num_re = regex.compile(r"([0-9.,]*[0-9])")
        self.alphabet =  "aàáảãạăằắẳẵặâầấẩẫậeèéẻẽẹêềếểễệiìíỉĩịoòóỏõọôồốổỗộơờớởỡợuùúủũụưừứửữựyỳýỷỹỵbcdđghklmnpqrstvx"
        self.keep_text_and_num_re = regex.compile(rf"[^\s{self.alphabet}.,0-9]")
        self.keep_text_re = regex.compile(rf"[^\s{self.alphabet}]")
        self.special_char = ['vov','vtv']
        self.speak_special_char = ['vê ô vê', 'vê tê vê']
        
    def read_number(self, num: str) -> str:
        if len(num) == 1:
            return self.digits[int(num)]
        elif len(num) == 2 and num.isdigit():
            n = int(num)
            end = self.digits[n % 10]
            if n == 10:
                return "mười"
            if n % 10 == 5:
                end = "lăm"
            if n % 10 == 0:
                return self.digits[n // 10] + " mươi"
            elif n < 20:
                return "mười " + end
            else:
                if n % 10 == 1:
                    end = "mốt"
                return self.digits[n // 10] + " mươi " + end
        elif len(num) == 3 and num.isdigit():
            n = int(num)
            if n % 100 == 0:
                return self.digits[n // 100] + " trăm"
            elif num[1] == "0":
                return self.digits[n // 100] + " trăm lẻ " + self.digits[n % 100]
            else:
                return self.digits[n // 100] + " trăm " + self.read_number(num[1:])
        elif len(num) >= 4 and len(num) <= 6 and num.isdigit():
            n = int(num)
            n1 = n // 1000
            return self.read_number(str(n1)) + " ngàn " + self.read_number(num[-3:])
        elif "," in num:
            n1, n2 = num.split(",")
            return self.read_number(n1) + " phẩy " + self.read_number(n2)
        elif "." in num:
            parts = num.split(".")
            if len(parts) == 2:
                if parts[1] == "000":
                    return self.read_number(parts[0]) + " ngàn"
                elif parts[1].startswith("00"):
                    end = self.digits[int(parts[1][2:])]
                    return self.read_number(parts[0]) + " ngàn lẻ " + end
                else:
                    return self.read_number(parts[0]) + " ngàn " + self.read_number(parts[1])
            elif len(parts) == 3:
                return (
                    self.read_number(parts[0])
                    + " triệu "
                    + self.read_number(parts[1])
                    + " ngàn "
                    + self.read_number(parts[2])
                )
        return num
    #fix custom speck special character 
    def read_custom_character(self,char:str):
        for index,character in enumerate(self.special_char):
            if character.strip() in char:
               char =  char.replace(character,self.speak_special_char[index])
        return char
    
    def text_to_phone_idx(self, text):
        # lowercase
        text = text.lower()
        # unicode normalize
        text = unicodedata.normalize("NFKC", text)
        text = text.replace(".", " . ")
        text = text.replace(",", " , ")
        text = text.replace(";", " ; ")
        text = text.replace(":", " : ")
        text = text.replace("!", " ! ")
        text = text.replace("?", " ? ")
        text = text.replace("(", " ( ")

        text = self.num_re.sub(r" \1 ", text)
        words = text.split()
        words = [self.read_number(w) if self.num_re.fullmatch(w) else w for w in words]
        text = " ".join(words)

        # remove redundant spaces
        text = regex.sub(r"\s+", " ", text)
        # remove leading and trailing spaces
        text = text.strip()
        text = self.read_custom_character(text)
        print('*'*20,'#ntext : ',text)
        # convert words to phone indices
        tokens = []
        for c in text:
            # if c is "," or ".", add <sil> phone
            if c in ":,.!?;(":
                tokens.append(self.sil_idx)
            elif c in self.phone_set:
                tokens.append(self.phone_set.index(c))
            elif c == " ":
                # add <sep> phone
                tokens.append(0)
        if tokens[0] != self.sil_idx:
            # insert <sil> phone at the beginning
            tokens = [self.sil_idx, 0] + tokens
        if tokens[-1] != self.sil_idx:
            tokens = tokens + [0, self.sil_idx]
        return tokens

    def text_to_speech(self, duration_net, generator, text):
        # prevent too long text
        if len(text) > 500:
            text = text[:500]

        phone_idx = self.text_to_phone_idx(text)
        batch = {
            "phone_idx": np.array([phone_idx]),
            "phone_length": np.array([len(phone_idx)]),
        }
        # predict phoneme duration
        phone_length = torch.from_numpy(batch["phone_length"].copy()).long().to(self.device)
        phone_idx = torch.from_numpy(batch["phone_idx"].copy()).long().to(self.device)
        with torch.inference_mode():
            phone_duration = duration_net(phone_idx, phone_length)[:, :, 0] * 1000
        phone_duration = torch.where(
            phone_idx == self.sil_idx, torch.clamp_min(phone_duration, 200), phone_duration
        )
        phone_duration = torch.where(phone_idx == 0, 0, phone_duration)

        # generate waveform
        end_time = torch.cumsum(phone_duration, dim=-1)
        start_time = end_time - phone_duration
        start_frame = start_time / 1000 * self.hps.data.sampling_rate / self.hps.data.hop_length
        end_frame = end_time / 1000 * self.hps.data.sampling_rate / self.hps.data.hop_length
        spec_length = end_frame.max(dim=-1).values
        pos = torch.arange(0, spec_length.item(), device=self.device)
        attn = torch.logical_and(
            pos[None, :, None] >= start_frame[:, None, :],
            pos[None, :, None] < end_frame[:, None, :],
        ).float()
        with torch.inference_mode():
            y_hat = generator.infer(
                phone_idx, phone_length, spec_length, attn, max_len=None, noise_scale=0.0
            )[0]
        wave = y_hat[0, 0].data.cpu().numpy()
        return (wave * (2**15)).astype(np.int16)

    def load_models(self):
        duration_net = DurationNet(self.hps.data.vocab_size, 64, 4).to(self.device)
        duration_net.load_state_dict(torch.load(self.duration_model_path, map_location=self.device))
        duration_net = duration_net.eval()

        generator = SynthesizerTrn(
            self.hps.data.vocab_size,
            self.hps.data.filter_length // 2 + 1,
            self.hps.train.segment_size // self.hps.data.hop_length,
            **vars(self.hps.model),
        ).to(self.device)
        del generator.enc_q
        ckpt = torch.load(self.lightspeed_model_path, map_location=self.device)
        params = {}
        for k, v in ckpt["net_g"].items():
            k = k[7:] if k.startswith("module.") else k
            params[k] = v
        generator.load_state_dict(params, strict=False)
        del ckpt, params
        generator = generator.eval()
        return duration_net, generator

    def speak(self, text,duration_net,generator):
        # duration_net, generator = self.load_models()
        paragraphs = text.split("\n")
        clips = []  # list of audio clips
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if paragraph == "":
                continue
            clips.append(self.text_to_speech(duration_net, generator, paragraph))
        y = np.concatenate(clips)
        return self.hps.data.sampling_rate, y




# # Paths to files
# config_file = "./../../../config/text2speech/config.json"
# duration_model_path = "./../../../models/duration_model.pth"
# lightspeed_model_path = "./../../../models/gen_630k.pth"
# phone_set_file = "./../../../config/text2speech/phone_set.json"
# device = "cuda" if torch.cuda.is_available() else "cpu"
# # Load configuration and phone set
# with open(config_file, "r") as f:
#     hps = json.load(f, object_hook=lambda x: SimpleNamespace(**x))
#     f.close()
# with open(phone_set_file, "r") as f:
#     phone_set = json.load(f)
#     f.close()

# assert phone_set[0][1:-1] == "SEP"
# assert "sil" in phone_set
# sil_idx = phone_set.index("sil")


# text2speech = Text2Speech(
#     hps=hps,
#     phone_set=phone_set,
#     sil_idx=sil_idx,
#     config_file=config_file,
#     duration_model_path=duration_model_path,
#     lightspeed_model_path=lightspeed_model_path,
#     phone_set_file=phone_set_file,
#     device=device,
# )


# sampling_rate, output = text2speech.speak('xin chào buổi sáng với 20 cốc cà phê')

# file_path = "./outputs/output.wav"

# sf.write(file_path, output, sampling_rate)

# print(f"Audio has been saved to {file_path}")
