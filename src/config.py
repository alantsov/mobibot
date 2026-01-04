import os
from dataclasses import dataclass

from omegaconf import OmegaConf


@dataclass
class AppConfig:
    output_format: str = "epub"
    start_from: str | None = None
    translate_to: str | None = None  # e.g. 'en'
    models_dir: str | None = os.path.join(os.getcwd(), "models")
    ollama_models_dir: str | None = os.path.join(os.getcwd(), "models", "ollama_models")
    use_whisper_prompt: bool = False
    diarize: bool = False
    simplify_transcript: bool = False


CONFIG: AppConfig | None = None


def init_config(*, config_path: str | None = None, cli_args: dict | None = None):
    global CONFIG
    if CONFIG is not None:
        print("!!!!!Config is already initialized!!!!!")
        print(CONFIG)
    cfg = OmegaConf.structured(AppConfig)
    if config_path and os.path.exists(config_path):
        yaml_cfg = OmegaConf.load(config_path)
        cfg.merge_with(yaml_cfg)
    if cli_args:
        cli_cfg = OmegaConf.create(cli_args)
        cfg.merge_with(cli_cfg)
    OmegaConf.set_readonly(cfg, True)
    CONFIG = cfg
    return cfg


def get_config() -> AppConfig:
    if CONFIG is None:
        init_config(config_path="config.yaml")
        print(CONFIG)
        print("!!!!!!Config is not initialized properly.!!!!!")
    return CONFIG
