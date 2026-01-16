# MobiBot WeSpeaker Dockerfile
# - Provides a CLI to run diarization and output JSON segments
#
# References:
# https://github.com/wenet-e2e/wespeaker

FROM pytorch/pytorch:2.4.1-cuda12.1-cudnn9-runtime

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    XDG_CACHE_HOME=/.cache

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv \
    git ffmpeg wget ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Ensure "python" exists
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3 1

# torchaudio to match PyTorch
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cu121 \
        torchaudio==2.4.1

# WeSpeaker
RUN pip install --no-cache-dir "git+https://github.com/wenet-e2e/wespeaker.git@7d7b707e927ad5cebfeb4ab4877c69fc64632bb2"
RUN pip install --no-cache-dir "scikit-learn<1.6.0" "umap-learn" "hdbscan"

# App code
WORKDIR /app

RUN mkdir /.cache && mkdir /.wespeaker

RUN python3 - <<EOF
import wespeaker
model = wespeaker.load_model('english')
model2 = wespeaker.load_model('vblinkf')
EOF

RUN chmod -R 777 /.cache
RUN chmod -R 777 /.wespeaker

COPY run_wespeaker.py /app/run_wespeaker.py

VOLUME ["/data"]

ENTRYPOINT ["python", "/app/run_wespeaker.py"]