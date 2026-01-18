FROM ghcr.io/jim60105/whisperx:no_model

RUN mkdir -p /nltk_data

RUN python3 - <<EOF
import nltk
nltk.download("punkt")
nltk.download("punkt_tab")
EOF

RUN chmod -R 777 /nltk_data

ENV TRANSFORMERS_CACHE=/models/hf
ENV TORCH_HOME=/models/torch
ENV XDG_CACHE_HOME=/models/xdg
ENV HF_HOME="$TRANSFORMERS_CACHE"
ENV MPLCONFIGDIR=/tmp/matplotlib

ENTRYPOINT ["whisperx"]
