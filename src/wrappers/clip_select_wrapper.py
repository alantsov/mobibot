import json
import logging
import os
import subprocess
import uuid

from src.wrappers import docker_wrapper

logger = logging.getLogger(__name__)


def select_screenshots_by_CLIP_model(image_folder: str):
    result = subprocess.run(["pwd"], capture_output=True, text=True, check=True)
    pwd = result.stdout.strip()
    data_root = os.path.join(pwd, "data")

    # Normalize input to be relative to data/
    if os.path.isabs(image_folder):
        raise ValueError(
            f"image_folder must be a relative path under data/. Got absolute path: {image_folder}"
        )

    normalized = os.path.normpath(image_folder).lstrip(os.sep)
    if normalized.startswith("data" + os.sep):
        normalized = normalized.split(os.sep, 1)[1]
    elif normalized == "data":
        normalized = ""

    full_path_host = os.path.normpath(os.path.join(data_root, normalized))

    # Basic validation
    if not os.path.isdir(full_path_host):
        raise FileNotFoundError(f"Images directory not found: {full_path_host}")

    rel_to_data = os.path.relpath(full_path_host, data_root)

    output_file = f"clip_select_output_{uuid.uuid4()}.json"
    cont_output_file = os.path.join("/data", output_file)
    command = ["--images_dir", rel_to_data, "--output_path", cont_output_file]
    result = docker_wrapper.run_docker_container("clip_select", command)
    if result.returncode != 0:
        logger.debug(
            "clip_select container failed.\nSTDOUT:\n%s\nSTDERR:\n%s", result.stdout, result.stderr
        )
        return [], 0
    try:
        with open(os.path.join(data_root, output_file), encoding="utf-8") as f:
            json_text = f.read()
        payload = json.loads(json_text)
        selected = payload.get("selected", [])
        total = payload.get("total", 0)
        return selected, total
    except Exception:
        logger.debug("failed to parse json %s", output_file)
        return [], 0
