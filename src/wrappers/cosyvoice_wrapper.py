import logging
import os

from src.config import get_config
from src.helpers.filepath_helper import generate_random_filename
from src.wrappers import docker_wrapper

logger = logging.getLogger(__name__)

def tts(input_md_relative):
    ext = get_config().output_format
    output_audio_relative = generate_random_filename('output', ext)
    command = [
        os.path.normpath(input_md_relative),
        os.path.normpath(output_audio_relative)
    ]
    result = docker_wrapper.run_docker_container("cosyvoice", command)
    if result.returncode != 0:
        logger.error("CosyVoice stdout: %s", result.stdout)
        logger.error("CosyVoice stderr: %s", result.stderr)
        raise RuntimeError(f"CosyVoice processing failed with return code {result.returncode}")
    return output_audio_relative
