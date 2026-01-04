import json
import logging
import uuid

from src.helpers.filepath_helper import get_abs_path
from src.wrappers import docker_wrapper

logger = logging.getLogger(__name__)


def _run_fasttext_container(text: str) -> str | None:
    if not isinstance(text, str):
        return None
    payload_file = f"text_to_detect_{uuid.uuid4()}.txt"
    with open(get_abs_path(payload_file), "w", encoding="utf-8") as f:
        f.write(text)
    output_file = f"fasttext_langid_output_{uuid.uuid4()}.json"
    command = ["/data/" + payload_file, "/data/" + output_file]
    proc = docker_wrapper.run_docker_container("fasttext", command)
    if proc.returncode != 0:
        logger.error(
            "fasttext_langid container failed.\nSTDOUT:\n%s\nSTDERR:\n%s", proc.stdout, proc.stderr
        )
    try:
        json_file = get_abs_path(output_file)
        with open(json_file, encoding="utf-8") as f:
            json_text = f.read()
        data = json.loads(json_text)
        lang = data.get("language")
        if isinstance(lang, str) or lang is None:
            logger.debug("Detected language: %s", lang)
            return lang
    except Exception:
        return None
    return None


def detect_language(text: str) -> str | None:
    """
    Detect the language of a given text using the FastText Dockerized service.

    Args:
        text (str): Input text.

    Returns:
        str | None: ISO language code (e.g., 'en', 'ru') or None if not detected.
    """
    return _run_fasttext_container(text)


if __name__ == "__main__":
    print(
        detect_language(
            "Как и в любой библиотеке, просьба соблюдать чистоту, порядок и спокойствие. Здесь читают и работают хорошие люди."
        )
    )
