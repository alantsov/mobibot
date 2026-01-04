import os

from src.wrappers import docker_wrapper


def convert_djvu(input_file, output_file):
    project_root = os.path.abspath("./data")
    in_path = os.path.relpath(os.path.abspath(input_file), project_root)
    out_path = os.path.relpath(os.path.abspath(output_file), project_root)
    os.makedirs(os.path.dirname(os.path.abspath(output_file)) or ".", exist_ok=True)

    # Image entrypoint is ddjvu, so omit the binary in args
    docker_wrapper.run_docker_container("djvu", ["-format=pdf", in_path, out_path])
    return output_file
