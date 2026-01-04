from src.wrappers import docker_wrapper


def _run_pandoc_in_docker(pandoc_args, workdir="data"):
    return docker_wrapper.run_docker_container("pandoc", pandoc_args)
