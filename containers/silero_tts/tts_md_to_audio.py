import os
import sys
import subprocess
import urllib.request
from torch import package
import torch

MODEL_DIR = "/models"
DATA_DIR = "/data"
MODEL_PATH = os.path.join(MODEL_DIR, "v5_1_ru.pt")
MODEL_URL = "https://models.silero.ai/models/tts/ru/v5_1_ru.pt"

torch.set_num_threads(8)
BLOCK_SIZE = 150


def ensure_model():
    os.makedirs(MODEL_DIR, exist_ok=True)
    if not os.path.exists(MODEL_PATH):
        print("Downloading TTS model...")
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
        print("Model downloaded")


def load_model():
    imp = package.PackageImporter(MODEL_PATH)
    return imp.load_pickle("tts_models", "model")


def split_into_sentences(text):
    """Split text into sentences based on sentence endings."""
    sentence_endings = [".", "?", "!"]
    if not text:
        return []

    sentences = []
    current = ""

    for char in text:
        current += char
        if char in sentence_endings:
            if current.strip():
               sentences.append(current.strip())
            current = ""

    if current.strip():
        sentences.append(current.strip())

    return sentences


def join_lines(lines):
    lines = [l for l in lines if l.strip()]

    # Split each line into sentences first
    all_sentences = []
    for line in lines:
        all_sentences.extend(split_into_sentences(line))

    if not all_sentences:
        return []

    result = [all_sentences[0]]
    skipped_line = False

    for sentence in all_sentences[1:]:
        if not sentence:
            skipped_line = True
            continue

        last = result[-1]

        if last and last[-1] in ".!?":
            result.append(sentence)
        elif (
                last
                and not skipped_line
                and sentence[0].isalpha()
                and (last[-1].isalpha() or last[-1] in ",:;")
        ):
            result[-1] += " " + sentence
        else:
            result.append(sentence)

        skipped_line = False

    return result


def split_text_into_blocks(text):
    lines = join_lines(text.split("\n"))
    blocks = [lines[0]]
    for line in lines[1:]:
        if len(blocks[-1] + "\n" + line) < BLOCK_SIZE:
            blocks[-1] += "\n" + line
        else:
            blocks.append(line)
    return blocks


def write_wav(text, wav_path, model):
    blocks = split_text_into_blocks(text)
    audio_parts = []

    for i, block in enumerate(blocks, 1):
        print(f"Block {i}: {len(block)} chars")
        audio_parts.append(
            model.apply_tts(
                text=block,
                speaker="eugene",
                sample_rate=48000,
            )
        )

    audio = torch.cat(audio_parts, dim=0)
    model.packages[0].write_wave(
        path=wav_path,
        audio=(audio * 32767).numpy().astype("int16"),
        sample_rate=48000,
    )


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

    ensure_model()
    model = load_model()

    with open(input_md, "r", encoding="utf-8") as f:
        text = f.read()

    tmp_wav = output_path + ".tmp.wav"

    write_wav(text, tmp_wav, model)
    convert_audio(tmp_wav, output_path)

    print("Done:", output_path)
