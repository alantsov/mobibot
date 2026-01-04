import os
import subprocess

from src.wrappers import docker_wrapper


def audio_to_json(input_name, language="ru", prompt=None):
    pwd = subprocess.run(["pwd"], capture_output=True, text=True, check=True).stdout.strip()
    data_root = os.path.join(pwd, "data")
    if os.path.isabs(input_name):
        raise ValueError("input_name must be relative under data/")
    full_path_host = os.path.join(data_root, os.path.normpath(input_name))
    container_input_path = "/data/" + os.path.basename(full_path_host)
    command = [
        "--output_format",
        "json",
        "--model",
        "large-v2",
        "--vad_method",
        "silero",
        "--beam_size",
        "10",
        "--temperature",
        "0",
        "--language",
        language,
        "--output_dir",
        "/data",
    ]
    if prompt:
        command += ["--initial_prompt", prompt]
    command += [container_input_path]
    result = docker_wrapper.run_docker_container("whisperx", command)
    if result.returncode != 0:
        raise RuntimeError("WhisperX processing failed")
    output_json = os.path.splitext(input_name)[0] + ".json"
    return output_json
