import os
from dataclasses import dataclass

import src.config as config

"""
config how to build and run containers
key would be folder name inside `containers`
"""


# container can expose only one port
@dataclass(frozen=True)
class DockerConfig:
    name: str
    port_container: int = None
    port_host: int = None
    image_name: str = None
    use_gpu: bool = False
    detached: bool = True
    env_vars: dict = None
    use_host_user: bool = True
    rm: bool = True
    volumes: list[str] = None  # strings formatted as host:container
    work_dir: str = None
    ping_path: str = None


DATA_DIR = f"{os.getcwd()}/data"
PROJECT_PREFIX = "mobibot"


def get_containers_config(svc: str) -> DockerConfig:
    MODELS_DIR = config.get_config().models_dir
    OLLAMA_MODELS_DIR = config.get_config().ollama_models_dir

    for model_dir in [MODELS_DIR, OLLAMA_MODELS_DIR]:
        os.makedirs(model_dir, exist_ok=True)

    calibre_config = DockerConfig(
        name="calibre",
        image_name=f"{PROJECT_PREFIX}/calibre:1.0.0",
        work_dir="/work",
        volumes=[f"{DATA_DIR}:/work"],
    )

    clip_select_config = DockerConfig(
        name="clip_select",
        image_name=f"{PROJECT_PREFIX}/clip_select:1.0.0",
        volumes=[f"{DATA_DIR}:/data"],
    )

    djvu_config = DockerConfig(
        name="djvu",
        image_name=f"{PROJECT_PREFIX}/djvu:1.0.0",
        work_dir="/work",
        volumes=[f"{DATA_DIR}:/work"],
    )

    fasttext_config = DockerConfig(
        name="fasttext",
        image_name=f"{PROJECT_PREFIX}/fasttext:1.0.0",
        volumes=[f"{DATA_DIR}:/data"],
    )

    ffmpeg_config = DockerConfig(
        name="ffmpeg",
        image_name=f"{PROJECT_PREFIX}/ffmpeg:1.0.0",
        work_dir="/work",
        volumes=[f"{DATA_DIR}:/work"],
    )

    pandoc_config = DockerConfig(
        name="pandoc",
        image_name=f"{PROJECT_PREFIX}/pandoc:1.0.0",
        work_dir="/data",
        volumes=[f"{DATA_DIR}:/data"],
    )

    poppler_config = DockerConfig(
        name="poppler", image_name=f"{PROJECT_PREFIX}/poppler:1.0.0", volumes=[f"{DATA_DIR}:/data"]
    )

    pymorphy3_config = DockerConfig(
        name="pymorphy3", image_name=f"{PROJECT_PREFIX}/pymorphy3:1.0.0"
    )

    wespeaker_config = DockerConfig(
        name="wespeaker",
        image_name=f"{PROJECT_PREFIX}/wespeaker:1.0.8",
        use_gpu=True,
        volumes=[f"{DATA_DIR}:/data"],
        work_dir="/data",
    )

    whisperx_config = DockerConfig(
        name="whisperX",
        image_name=f"{PROJECT_PREFIX}/whisperx:1.0.1",
        volumes=[f"{DATA_DIR}:/data", f"{MODELS_DIR}:/models"],
        use_gpu=True,
    )

    yt_dlp_config = DockerConfig(
        name="yt_dlp",
        image_name=f"{PROJECT_PREFIX}/yt_dlp:1.0.0",
        volumes=[f"{DATA_DIR}:/download"],
    )

    ollama_config = DockerConfig(
        name="ollama",
        port_container=11434,
        port_host=11435,
        image_name=f"{PROJECT_PREFIX}/ollama:1.0.1",
        use_gpu=True,
        volumes=[f"{OLLAMA_MODELS_DIR}:/root/.ollama/models"],
        ping_path="/api/tags",
        env_vars={"OLLAMA_FLASH_ATTENTION": "1"},
    )

    readability_config = DockerConfig(
        name="readability",
        port_container=3000,
        port_host=37544,
        ping_path="/",
        image_name=f"{PROJECT_PREFIX}/readability:1.0.0",
    )

    languagetool_config = DockerConfig(
        name="languagetool",
        port_container=8010,
        port_host=8011,
        ping_path="/",
        image_name=f"{PROJECT_PREFIX}/languagetool:1.0.0",
    )

    tiktoken_config = DockerConfig(
        name="tiktoken",
        port_container=8300,
        port_host=8300,
        ping_path="/ping",
        image_name=f"{PROJECT_PREFIX}/tiktoken:1.0.0",
    )

    cosyvoice_config = DockerConfig(
        name="cosyvoice",
        image_name=f"{PROJECT_PREFIX}/cosyvoice:1.0.0",
        volumes=[f"{DATA_DIR}:/data", f"{MODELS_DIR}:/models"],
        use_gpu=True,
    )

    containers_configs = {
        "calibre": calibre_config,
        "clip_select": clip_select_config,
        "djvu": djvu_config,
        "fasttext": fasttext_config,
        "ffmpeg": ffmpeg_config,
        "pandoc": pandoc_config,
        "poppler": poppler_config,
        "pymorphy3": pymorphy3_config,
        "wespeaker": wespeaker_config,
        "whisperx": whisperx_config,
        "yt_dlp": yt_dlp_config,
        "ollama": ollama_config,
        "readability": readability_config,
        "languagetool": languagetool_config,
        "tiktoken": tiktoken_config,
        "cosyvoice": cosyvoice_config,
    }
    return containers_configs[svc]
