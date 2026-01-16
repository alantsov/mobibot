FROM pytorch/pytorch:2.1.2-cuda12.1-cudnn8-runtime

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    git \
    git-lfs \
    ffmpeg \
    build-essential \
    libsox-dev \
    unzip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Clone CosyVoice repository
RUN git clone --recursive https://github.com/FunAudioLLM/CosyVoice.git /app

# Install dependencies from the repository
RUN pip install --no-cache-dir -r requirements.txt

RUN pip install --no-cache-dir huggingface_hub

# Install ttsfrd during build
RUN mkdir -p /app/pretrained_models && \
    python3 -c "from huggingface_hub import snapshot_download; snapshot_download('FunAudioLLM/CosyVoice-ttsfrd', local_dir='/app/pretrained_models/CosyVoice-ttsfrd')" && \
    cd /app/pretrained_models/CosyVoice-ttsfrd/ && \
    unzip resource.zip -d . && \
    pip install ttsfrd_dependency-0.1-py3-none-any.whl && \
    pip install ttsfrd-0.4.2-cp310-cp310-linux_x86_64.whl

RUN pip install --upgrade PyYAML hyperpyyaml

COPY cli.py /app/cli.py
COPY prompt_audio_3_ru.wav /app/asset/prompt_audio_3_ru.wav

# Create directories for models and data, and set permissions for -u argument
RUN mkdir -p /models /data && chmod 777 /models /data /app && chmod -R 777 /app && chmod 777 /tmp
RUN git config --global --add safe.directory /app

# Set environment variables for model caches
ENV PYTHONPATH=/app:/app/third_party/Matcha-TTS
ENV MODEL_DIR=/models
ENV DATA_DIR=/data
ENV HF_HOME=/models/hf
ENV TORCH_HOME=/models/torch
ENV MODELSCOPE_CACHE=/models/modelscope
ENV HOME=/tmp

ENTRYPOINT ["python3", "cli.py"]
