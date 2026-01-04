# CLIP-based screenshot selection container
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OPENCLIP_CACHE_DIR=/opt/openclip-cache \
    TORCH_HOME=/opt/torch-cache \
    HF_HOME=/opt/hf-cache \
    XDG_CACHE_HOME=/tmp

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p $OPENCLIP_CACHE_DIR $TORCH_HOME $HF_HOME && \
    chmod -R a+rX $OPENCLIP_CACHE_DIR $TORCH_HOME $HF_HOME

WORKDIR /app

RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu && \
    pip install git+https://github.com/openai/CLIP.git numpy pillow

COPY select_screenshots.py /app/select_screenshots.py

RUN python - <<'PY'
import os
import torch
import clip
print('ENV OPENCLIP_CACHE_DIR=', os.environ.get('OPENCLIP_CACHE_DIR'))
print('ENV TORCH_HOME=', os.environ.get('TORCH_HOME'))
device = "cpu"
model, preprocess = clip.load("ViT-B/32", device=device, download_root='/opt/openclip-cache')
from PIL import Image
img = Image.new('RGB', (224,224), color=(255,255,255))
_ = preprocess(img).unsqueeze(0).to(device)
print("CLIP ViT-B/32 weights preloaded into caches")
os.system(f"chmod -R a+rX {os.environ['OPENCLIP_CACHE_DIR']} {os.environ['TORCH_HOME']} {os.environ['HF_HOME']}")
PY

ENTRYPOINT ["python", "/app/select_screenshots.py"]
