import os
import sys
import subprocess
sys.path.append('third_party/Matcha-TTS')
from cosyvoice.cli.cosyvoice import AutoModel
import torchaudio
import torch
from huggingface_hub import snapshot_download

MODEL_DIR = os.getenv("MODEL_DIR", "/models")
DATA_DIR = os.getenv("DATA_DIR", "/data")

def tts(text, output_path):
    model_path = os.path.join(MODEL_DIR, 'Fun-CosyVoice3-0.5B')
    if not os.path.exists(model_path):
        print(f"Downloading model to {model_path}...")
        snapshot_download('FunAudioLLM/Fun-CosyVoice3-0.5B-2512', local_dir=model_path)
    
    cosyvoice = AutoModel(model_dir=model_path)

    pause_sec = 0.6
    silence = torch.zeros(
        1, int(cosyvoice.sample_rate * pause_sec)
    )

    tts_chunks = []
    for line in text.split('\n'):
        if len(line.strip()) > 0:
            for i, j in enumerate(cosyvoice.inference_cross_lingual('You are a helpful assistant. speak clearly without background noise<|endofprompt|>'+line,
                                                                '/app/asset/prompt_audio_3_ru.wav', stream=False)):
                tts_chunks.append(j['tts_speech'])
            tts_chunks.append(silence)
    tts_speach = torch.cat(tts_chunks, dim=1)
    torchaudio.save(output_path, tts_speach, cosyvoice.sample_rate)

def convert_audio(src_wav, dst_path):
    ext = os.path.splitext(dst_path)[1].lower()

    if ext == ".wav":
        os.replace(src_wav, dst_path)
        return

    codecs = {
        ".mp3": ["-codec:a", "libmp3lame", "-q:a", "2"],
        ".ogg": ["-codec:a", "libvorbis", "-q:a", "5"],
        ".aac": ["-codec:a", "aac", "-b:a", "192k"],
    }

    if ext not in codecs:
        raise ValueError(f"Unsupported output format: {ext}")

    cmd = [
        "ffmpeg",
        "-y",
        "-loglevel", "error",
        "-i", src_wav,
        *codecs[ext],
        dst_path,
    ]

    subprocess.run(cmd, check=True)
    os.remove(src_wav)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python tts_md_to_audio.py <input.md> <output.(wav|mp3|ogg|aac)>")
        sys.exit(1)

    input_md = os.path.join(DATA_DIR, sys.argv[1])
    output_path = os.path.join(DATA_DIR, sys.argv[2])

    if not os.path.exists(input_md):
        raise FileNotFoundError(input_md)

    with open(input_md, "r", encoding="utf-8") as f:
        text = f.read()

    tmp_wav = output_path + ".tmp.wav"

    tts(text, tmp_wav)
    convert_audio(tmp_wav, output_path)

    print("Done:", output_path)