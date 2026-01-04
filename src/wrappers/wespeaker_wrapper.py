import logging
import os

from src.helpers.filepath_helper import generate_random_filename, get_abs_path, get_rel_path
from src.wrappers import docker_wrapper

logger = logging.getLogger(__name__)


def diarize(audio_path, language="en"):
    audio_path = get_rel_path(audio_path)
    json_path = generate_random_filename("diarize", "json")
    command = ["--", audio_path, json_path, language]
    result = docker_wrapper.run_docker_container("wespeaker", command)
    if not os.path.isfile(get_abs_path(json_path)):
        logger.error("wespeaker failed to generate json file: %s", result.stderr)
        logger.debug("wespeaker stdout:\n%s", result.stdout)
        return None
    return json_path
