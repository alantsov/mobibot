import logging
import os
import subprocess
import time

import docker
from docker.errors import APIError

from src.wrappers import docker_config_wrapper

logger = logging.getLogger(__name__)

_client = None


def _get_docker_client():
    global _client
    if _client is None:
        _client = docker.from_env()
    return _client


# with ManagedDockerService('ollama') as ollama_service:
#     ollama_wrapper.set_ollama_port(ollama_service.ports[0])
#     result = ollama_wrapper.parse_image(...)
class ManagedDockerService:
    def __init__(self, service_name):  # or service_name
        self.service_name = service_name  # directory_name inside containers/
        self.config = docker_config_wrapper.get_containers_config(service_name)

        self.container = None
        self.client = _get_docker_client()
        _ensure_docker_image(self.config.image_name, service_name)
        self._start()

    @property
    def port(self):
        self.container.reload()
        port_bindings = self.container.attrs["NetworkSettings"]["Ports"]
        container_port_key = f"{self.config.port_container}/tcp"
        if container_port_key in port_bindings and port_bindings[container_port_key]:
            return int(port_bindings[container_port_key][0]["HostPort"])
        return self.config.port_host

    @property
    def base_url(self) -> str:
        return f"http://localhost:{self.port}"

    def _start(self):
        run_config = {}
        run_config["ports"] = {self.config.port_container: self.config.port_host}
        run_config["detach"] = True
        if self.config.volumes:
            run_config["volumes"] = (
                self.config.volumes
            )  # each str in list formatted as host_path:container_path
        if self.config.use_gpu:
            run_config["device_requests"] = [
                docker.types.DeviceRequest(count=-1, capabilities=[["gpu"]])
            ]
        try:
            self.container = self.client.containers.run(self.config.image_name, **run_config)
        except APIError as e:
            logger.warning(f"Failed to start docker container {self.config.image_name}: {e}")
            run_config["ports"] = {self.config.port_container: None}
            self.container = self.client.containers.run(self.config.image_name, **run_config)

    def __enter__(self):
        time.sleep(2)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.container:
            try:
                self.container.remove(force=True)
            except:
                pass


# for docker containers like whisperx: mount directory
def run_docker_container(
    container_name, container_arguments, capture_output=True
) -> subprocess.CompletedProcess:
    docker_config = docker_config_wrapper.get_containers_config(container_name)
    _ensure_docker_image(docker_config.image_name, container_name)
    docker_arguments = []
    if docker_config.use_gpu:
        docker_arguments += ["--gpus=all"]
    if docker_config.volumes:
        for volume in docker_config.volumes:
            docker_arguments += ["-v", volume]
    if docker_config.use_host_user:
        docker_arguments += ["-u", f"{os.getuid()}:{os.getgid()}"]
    if docker_config.work_dir:
        docker_arguments += ["-w", docker_config.work_dir]
    if docker_config.rm:
        docker_arguments += ["--rm"]
    command = (
        ["docker", "run"] + docker_arguments + [docker_config.image_name] + container_arguments
    )
    logger.debug("run_docker_container: %s", command)
    return subprocess.run(command, text=True, capture_output=True)


def _ensure_docker_image(image: str, image_folder) -> None:
    """
    build docker image if not exists.
    subprocess used intentionally instead of docker-py

    :param image:
    :param image_folder:
    :return: nothing, just raise an error if the Dockerfile is not found
    """
    inspected = subprocess.run(["docker", "image", "inspect", image], capture_output=True)
    if inspected.returncode == 0:
        return
    else:
        cmd = [
            "docker",
            "build",
            "-f",
            f"containers/{image_folder}/Dockerfile",
            "-t",
            image,
            f"containers/{image_folder}",
        ]

        env = os.environ.copy()
        env["DOCKER_BUILDKIT"] = "1"

        result = subprocess.run(cmd, env=env, text=True)
        result.check_returncode()
