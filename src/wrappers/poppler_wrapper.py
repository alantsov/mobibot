import os

from src.helpers.filepath_helper import generate_random_filename, get_abs_path, get_rel_path
from src.wrappers import docker_wrapper


def poppler_pdf_to_images(pdf_path: str):
    images_dir_inner = generate_random_filename("pages")
    images_dir = get_abs_path(images_dir_inner)
    os.makedirs(images_dir, exist_ok=True)
    prefix = f"/data/{images_dir_inner}/page"
    pdf_path_in_data = get_rel_path(pdf_path)

    pdf_container_path = f"/data/{pdf_path_in_data}"
    command = [pdf_container_path, prefix]
    docker_wrapper.run_docker_container("poppler", command)
    images = []
    for file in list(sorted(os.listdir(images_dir))):
        if file.endswith(".png"):
            images.append(images_dir + "/" + file)

    return images_dir_inner, images
