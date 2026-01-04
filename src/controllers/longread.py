import os
from dataclasses import dataclass
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from src.config import get_config
from src.controllers import pdf
from src.helpers import text_helper
from src.helpers.filepath_helper import generate_random_filename, get_abs_path, get_rel_path
from src.helpers.html_helper import (
    extract_cover_from_html,
    initial_html_clean_up,
    localize_images,
    preprocess_generic_page,
    render_latex,
    translate_html_file,
)
from src.loaders import longread_loader
from src.pipeline import (
    PipelineResource,
    PipelineStage,
    copy_arguments,
    fold_pipeline,
    get_last_pipeline_state,
    restart_stage,
    run_with_resources,
)
from src.wrappers import calibre_wrapper, ollama_wrapper, pillow_wrapper, readability_wrapper
from src.wrappers.docker_wrapper import ManagedDockerService


@dataclass
class Longread:
    url: str
    file_path: str | None = None
    link: str | None = None
    html_filename: str | None = None
    is_paper: bool | None = None
    preprocessed_file_name: str | None = None
    cleaned_filename: str | None = None
    latex_filename: str | None = None
    processed_filename: str | None = None
    translated_html_filename: str | None = None
    cover_url: str | None = None
    title: str | None = None
    author: str | None = None
    mobi_file_path: str | None = None
    cwd: str | None = "data"


OLLAMA_RES = PipelineResource(
    factory=lambda: ManagedDockerService("ollama"),
    setup=lambda service: ollama_wrapper.set_ollama_port(service.port),
)
READABILITY_RES = PipelineResource(
    factory=lambda: ManagedDockerService("readability"),
    setup=lambda service: readability_wrapper.set_readability_port(service.port),
)


def prepare_input(url, file_path):
    if file_path:
        html_filename = get_rel_path(file_path)
        pwd = os.getcwd()
        link = f"file://{pwd}/data/{html_filename}"
    else:
        link = replace_longread_url(url)
        html_filename = longread_loader.download_longread(link)
    return link, html_filename


def detect_latext_on_page(html_filename):
    with open(get_abs_path(html_filename), encoding="utf-8") as f:
        html_content = f.read()
    soup = BeautifulSoup(html_content, "html.parser")
    for math_tag in soup.find_all("math"):
        return True
    return False


def apply_readability(html_filename, link, is_paper):
    preprocessed_page, title, author = preprocess_generic_page(html_filename, link)
    author = (author or "").replace("\n", " ")
    if is_paper :
        return html_filename, title, author
    return preprocessed_page, title, author


def convert_to_mobi(processed_filename, title, cover_url, author):
    mobi_file_name = generate_random_filename(
        text_helper.clean_title(title), get_config().output_format
    )
    try:
        prepared_cover = pillow_wrapper.create_cover(
            cover_url or "/dev/null", title, author, cwd="data"
        )
    except Exception:
        prepared_cover = pillow_wrapper.create_cover("/dev/null", title, author, cwd="data")
    calibre_wrapper.convert_book(
        processed_filename,
        mobi_file_name,
        cwd="data",
        cover=prepared_cover,
        author=author,
        title=title,
    )
    return mobi_file_name


def get_pipeline():
    return [
        PipelineStage(
            prepare_input,
            ["url", "file_path"],
            ["link", "html_filename"],
            resources=[OLLAMA_RES, READABILITY_RES],
        ),
        PipelineStage(detect_latext_on_page, ["html_filename"], ["is_paper"]),
        PipelineStage(
            apply_readability,
            ["html_filename", "link", "is_paper"],
            ["preprocessed_file_name", "title", "author"],
            resources=[READABILITY_RES],
        ),
        PipelineStage(
            initial_html_clean_up, ["preprocessed_file_name", "link"], ["cleaned_filename"]
        ),
        PipelineStage(render_latex, ["cleaned_filename"], ["latex_filename"]),
        PipelineStage(localize_images, ["latex_filename", "link"], ["processed_filename"]),
        PipelineStage(
            translate_html_file,
            ["processed_filename"],
            ["translated_html_filename"],
            enabled=(get_config().translate_to is not None),
            resources=[OLLAMA_RES],
        ),
        PipelineStage(
            copy_arguments,
            ["processed_filename"],
            ["translated_html_filename"],
            enabled=(get_config().translate_to is None),
            _given_name="translate_html_file",
        ),
        PipelineStage(extract_cover_from_html, ["translated_html_filename"], ["cover_url"]),
        PipelineStage(
            convert_to_mobi,
            ["translated_html_filename", "title", "cover_url", "author"],
            ["mobi_file_path"],
        ),
    ]


def link2mobi(url, file_path=None):
    pipeline_state = get_last_pipeline_state(Longread, {"url": url, "file_path": file_path})
    if get_config().start_from and pipeline_state:
        longread, _ = restart_stage(
            get_config().start_from, get_pipeline(), pipeline_state, Longread
        )
        return longread.mobi_file_path
    else:
        link, html_filename = run_with_resources(
            prepare_input, [OLLAMA_RES, READABILITY_RES], [url, file_path]
        )
        if longread_loader.is_pdf_file(html_filename):
            return pdf.pdf_to_mobi(html_filename)
        longread = Longread(url=url, file_path=file_path, link=link, html_filename=html_filename)
        longread, _ = fold_pipeline(get_pipeline(), longread)
        return longread.mobi_file_path


def replace_longread_url(url):
    domain = urlparse(url).hostname
    if domain == "t.me":
        return url + "?embed=1&mode=tme"
    if domain in ["arxiv.org", "huggingface.co", "www.arxiv.org", "www.huggingface.co"]:
        if "huggingface" in domain and not urlparse(url).path.startswith("/papers/"):
            return url
        path = urlparse(url).path
        paper_id = path.rstrip("/").split("/")[-1]
        return f"https://arxiv.org/html/{paper_id}"
    return url
