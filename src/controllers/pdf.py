import logging
from dataclasses import dataclass, replace

from bs4 import BeautifulSoup
from tqdm import tqdm

import src.helpers.latex_helper
from src.config import get_config
from src.helpers import html_helper, latex_helper, text_helper
from src.helpers.filepath_helper import generate_random_filename, get_abs_path, get_rel_path
from src.pipeline import (
    PipelineResource,
    PipelineStage,
    copy_arguments,
    fold_pipeline,
    get_last_pipeline_state,
    restart_stage,
)
from src.wrappers import (
    calibre_wrapper,
    djvu_wrapper,
    ollama_wrapper,
    pillow_wrapper,
    poppler_wrapper,
    tiktoken_wrapper,
)
from src.wrappers.docker_wrapper import ManagedDockerService, NoManagedService
from src.wrappers.pandoc_wrapper import _run_pandoc_in_docker

logger = logging.getLogger(__name__)

# Resource dependency definitions
def _ollama_factory():
    cfg = get_config()
    if cfg and cfg.ollama_url:
        return NoManagedService()
    return ManagedDockerService("ollama")


def _ollama_setup(service):
    if service.port:
        ollama_wrapper.set_ollama_port(service.port)


OLLAMA_RES = PipelineResource(
    factory=_ollama_factory,
    setup=_ollama_setup,
)
TIKTOKEN_RES = PipelineResource(
    factory=lambda: ManagedDockerService("tiktoken"),
    setup=lambda service: tiktoken_wrapper.set_tiktoken_port(service.port),
)


@dataclass(frozen=True)
class DocumentBlock:
    page_number: int
    index: int
    block_type: str = "text"  # image image_caption text equation table table_caption table_footnote title sub_title
    bbox: str = None
    text: str = None  # none for image before merged with image_caption
    image_path: str = None
    tokens: int = None
    char_per_token: float = None


@dataclass
class PDFDocument:
    file_name: str
    pdf_file_name: str = None
    title: str = None
    author: str = None
    images_dir_inner: str = None
    images: list = None
    det_mmd_pages: list = None
    blocks: list[DocumentBlock] = None
    deduplicated_blocks: list[DocumentBlock] = None
    processed_blocks: list[DocumentBlock] = None
    processed_blocks_tokens: list[DocumentBlock] = None
    blocks_with_images: list[DocumentBlock] = None
    recovered_blocks: list[DocumentBlock] = None
    joined_blocks: list[DocumentBlock] = None
    final_blocks: list[DocumentBlock] = None
    md_filename_correct: str = None
    html_filename: str = None
    new_html_filename: str = None
    translated_html_filename: str = None
    cover_image: str = None
    mobi_file_path: str = None


def convert_markdown_to_html_pandoc(md_filename):
    """Convert markdown to HTML using pandoc (via Docker)."""
    html_filename = generate_random_filename("full_text", "html")
    # Rely on the image entrypoint (pandoc). Pass flags and paths relative to /data
    md_filename = get_rel_path(md_filename)
    _run_pandoc_in_docker(
        ["--mathjax", "--mathml", md_filename, "-o", html_filename], workdir="data"
    )
    return html_filename


def convert_html_with_mathml_to_html(html_filename):
    """Convert HTML with MathML to HTML using pandoc."""
    new_html_filename = generate_random_filename("full_text_with_math", "html")
    with open(get_abs_path(html_filename)) as f:
        html_content = f.read()
    soup = BeautifulSoup(html_content, "html.parser")
    soup = src.helpers.latex_helper.process_math(soup)
    with open(get_abs_path(new_html_filename), "w") as f:
        f.write(str(soup))
    return new_html_filename


def extract_title_and_author(images):
    image = get_rel_path(images[0])
    title, author = ollama_wrapper.extract_title_and_author_from_image(image)
    return title, author


def convert_to_mobi(html_filename, title, author, cover_image):
    """Convert HTML to e-book format based on output_format.

    - If output_format ends with 'epub': use pandoc in Docker to convert HTML → EPUB
      (still prepare a cover with Pillow and pass metadata).
    - Else (including 'mobi'): use Calibre for conversion as before.
    """
    ext = get_config().output_format

    # Prepare cover first using Pillow (used by both flows)
    try:
        prepared_cover = pillow_wrapper.create_cover(
            cover_image or "/dev/null", title, author, cwd="data"
        )
    except Exception:
        prepared_cover = pillow_wrapper.create_cover("/dev/null", title, author, cwd="data")

    title_for_filename = text_helper.clean_title(title)

    if ext == "epub":
        # Convert via pandoc in Docker
        epub_file_name = generate_random_filename(title_for_filename, "epub")
        # html_filename passed around pipeline is relative to data/, ensure relative for container
        html_in = get_rel_path(html_filename)
        cover_rel = get_rel_path(prepared_cover)
        pandoc_args = [
            html_in,
            "-o",
            epub_file_name,
            "--standalone",
            "--preserve-tabs",
            f"--epub-cover-image={cover_rel}",
            "--metadata",
            f"title={title}",
            "--metadata",
            f"author={author}",
        ]
        _run_pandoc_in_docker(pandoc_args, workdir="data")
        return epub_file_name

    # Default: use Calibre (keeps MOBI flow intact)
    output_file_name = generate_random_filename(title_for_filename, ext)
    calibre_wrapper.convert_book(
        html_filename,
        output_file_name,
        cwd="data",
        cover=prepared_cover,
        author=author,
        title=title,
    )
    return output_file_name


def handle_djvu(file_name):
    """Convert DJVU to PDF if needed."""
    if file_name.endswith(".djvu"):
        output_file_name = file_name + ".pdf"
        djvu_wrapper.convert_djvu(file_name, output_file_name)
        return output_file_name
    return file_name


def select_cover_image(images):
    return get_rel_path(images[0])


def get_pipeline():
    """Define the pipeline for PDF to MOBI conversion."""
    return [
        PipelineStage(handle_djvu, ["file_name"], ["pdf_file_name"]),
        PipelineStage(
            poppler_wrapper.poppler_pdf_to_images, ["pdf_file_name"], ["images_dir_inner", "images"]
        ),
        PipelineStage(images_to_det_mmd, ["images"], ["det_mmd_pages"], resources=[OLLAMA_RES]),
        PipelineStage(det_mmd_to_blocks, ["det_mmd_pages"], ["blocks"]),
        PipelineStage(deduplicate_blocks, ["blocks"], ["deduplicated_blocks"]),
        PipelineStage(process_blocks, ["deduplicated_blocks"], ["processed_blocks"]),
        PipelineStage(
            count_tokens_in_blocks,
            ["processed_blocks"],
            ["processed_blocks_tokens"],
            resources=[TIKTOKEN_RES],
        ),
        PipelineStage(split_images, ["processed_blocks_tokens", "images"], ["blocks_with_images"]),
        PipelineStage(
            recover_broken_blocks,
            ["blocks_with_images"],
            ["recovered_blocks"],
            resources=[OLLAMA_RES],
        ),
        PipelineStage(join_blocks, ["recovered_blocks"], ["joined_blocks"]),
        PipelineStage(fix_titles, ["joined_blocks"], ["final_blocks"], resources=[OLLAMA_RES]),
        PipelineStage(
            extract_title_and_author, ["images"], ["title", "author"], resources=[OLLAMA_RES]
        ),
        PipelineStage(blocks_to_md_file, ["final_blocks", "title"], ["md_filename_correct"]),
        PipelineStage(convert_markdown_to_html_pandoc, ["md_filename_correct"], ["html_filename"]),
        PipelineStage(convert_html_with_mathml_to_html, ["html_filename"], ["new_html_filename"]),
        PipelineStage(
            html_helper.translate_html_file,
            ["new_html_filename"],
            ["translated_html_filename"],
            enabled=(get_config().translate_to is not None),
            resources=[OLLAMA_RES],
        ),
        PipelineStage(
            copy_arguments,
            ["new_html_filename"],
            ["translated_html_filename"],
            enabled=(get_config().translate_to is None),
            _given_name="translate_html_file",
        ),
        PipelineStage(select_cover_image, ["images"], ["cover_image"]),
        PipelineStage(
            convert_to_mobi,
            ["translated_html_filename", "title", "author", "cover_image"],
            ["mobi_file_path"],
        ),
    ]


def images_to_det_mmd(images):
    result = []
    for image in tqdm(images):
        result.append(ollama_wrapper.ocr_with_deepseek_grounding(image))
    return result


def det_mmd_to_blocks(det_mmd_pages):
    """
    line samples:
    <|ref|>sub_title<|/ref|><|det|>[[54, 41, 368, 72]]<|/det|>
    <|ref|>text<|/ref|><|det|>[[52, 32, 912, 67]]<|/det|>

    """
    blocks = []
    for page_index, page in enumerate(det_mmd_pages):
        lines = page.split("\n")
        current_block_index = 0
        current_block_type = None
        current_bbox = None
        current_content = ""
        for line_o in lines:
            line = line_o.strip()
            if line.startswith("<|ref|>") and line.endswith("<|/det|>"):
                if current_block_type:
                    blocks.append(
                        DocumentBlock(
                            page_index,
                            current_block_index,
                            current_block_type,
                            current_bbox,
                            current_content,
                        )
                    )
                    current_block_index += 1
                current_bbox = line.split("<|/det|>")[0].split("<|det|>")[1]
                current_content = ""
                current_block_type = line.split("<|/ref|>")[0].split("<|ref|>")[1]
                if current_block_type == "title":
                    current_block_type = "sub_title"
            else:
                current_content += line + "\n"
        if current_block_type:
            blocks.append(
                DocumentBlock(
                    page_index,
                    current_block_index,
                    current_block_type,
                    current_bbox,
                    current_content,
                )
            )
            current_block_index += 1
    return blocks


def deduplicate_blocks(blocks):
    result = blocks[:1]
    for block in blocks[1:]:
        if block.page_number == result[-1].page_number and block.bbox == result[-1].bbox:
            continue
        else:
            result.append(block)
    return result


def process_blocks(blocks):
    result = []
    for block in blocks:
        if block.block_type in ["title", "sub_title"]:
            # "## 2 Background  \n\n" -> "2 Background"
            new_content = block.text.replace("#", "").strip()
            if r"\(" not in new_content:
                new_content = new_content.replace("- ", "")
                new_content = new_content.capitalize()
            if new_content:
                block2 = replace(block, text=new_content)
                result.append(block2)
        elif block.block_type == "equation":
            new_content = block.text.strip()
            new_content = new_content.replace("mathrm", "text")
            if new_content:
                block2 = replace(block, text=new_content)
                result.append(block2)
        elif block.block_type == "image_caption":
            new_content = block.text.strip()
            new_content = new_content.replace("<center>", "").replace("</center>", "").strip()
            if r"\(" not in new_content:
                new_content = new_content.replace("- ", "")
            if new_content:
                block2 = replace(block, text=new_content)
                result.append(block2)
        elif (
            block.block_type == "text" and block.text.upper() == block.text and len(block.text) < 64
        ):
            new_content = block.text.capitalize().strip()
            block2 = replace(block, text=new_content, block_type="sub_title")
            result.append(block2)
        elif block.block_type in ["table_caption", "table_footnote", "table"]:
            new_content = block.text.strip()
            lines = new_content.split("\n")
            lines = list(map(lambda x: x.strip("#").strip(), lines))
            new_content = "\n".join(lines)
            if new_content:
                block2 = replace(block, text=new_content)
                result.append(block2)
        elif block.block_type in ["text", "table_footnote", "table_caption", "table"]:
            new_content = block.text.strip()
            if new_content.startswith("#"):
                new_content = new_content.strip("#").strip()
            if r"\(" not in new_content:
                new_content = new_content.replace("- ", "")
            if new_content:
                block2 = replace(block, text=new_content)
                result.append(block2)
        elif block.block_type == "image":
            result.append(block)
        else:
            logger.error(f"Unknown block type: {block.block_type}")
    return result


def count_tokens_in_blocks(blocks):
    result = []
    for block in blocks:
        tokens = tiktoken_wrapper.encode(block.text)
        char_per_token = 0
        if len(tokens) > 0:
            char_per_token = len(block.text) / len(tokens)
        new_block = replace(block, tokens=len(tokens), char_per_token=char_per_token)
        result.append(new_block)
    return result


def split_images(blocks, images):
    result = []
    for block in tqdm(blocks):
        bbox = block.bbox
        image = images[block.page_number]
        bbox_list = bbox.replace("[", "").replace("]", "").split(", ")
        bbox_list = list(map(int, bbox_list))
        bbox_image = pillow_wrapper.crop_by_bbox(image, bbox_list, block.index)
        new_block = replace(block, image_path=get_rel_path(bbox_image))
        result.append(new_block)
    return result


def recover_broken_blocks(blocks):
    result = []
    for block in tqdm(blocks):
        if block.block_type in ["image", "equation"]:
            result.append(block)
        elif (
            (block.char_per_token > 2.0 or block.tokens < 5)
            and block.tokens < 500
            and "<td>None</td>" not in block.text
        ):
            # each normal block is under 500 tokens
            # sometimes deepseek-ocr repeat the same sequence until reached context window limit
            # sometimes deepseek-ocr provide table instead of normal text
            result.append(block)
        else:
            new_text = ollama_wrapper.ocr_with_deepseek(get_abs_path(block.image_path)).strip()
            new_text = new_text.strip("#").strip()
            new_text = new_text.replace(" \n", " ")
            if block.block_type == "sub_title":
                new_text = new_text.capitalize()
            if block.block_type in ["text", "table_footnote", "table_caption", "table"]:
                lines = new_text.split("\n")
                lines = list(map(lambda x: x.strip("#").strip(), lines))
                new_text = "\n".join(lines)
            if new_text:
                new_block = replace(block, text=new_text)
                result.append(new_block)
    return result


def join_blocks(blocks):
    result = blocks[:1]
    for block in blocks[1:]:
        if result[-1].block_type == "image" and block.block_type == "image_caption":
            new_text = result[-1].text + block.text
            new_text = new_text.strip()
            new_block = replace(result[-1], text=new_text)
            result[-1] = new_block
        elif (
            result[-1].block_type == "text"
            and block.block_type == "text"
            and block.text[:1] == block.text[:1].lower()
            and result[-1].text[-1].isalpha()
            and block.text[0].isalpha()
        ):
            new_text = result[-1].text + " " + block.text.strip()
            new_block = replace(block, text=new_text)
            result[-1] = new_block
        elif (
            result[-1].block_type == "text"
            and block.block_type == "text"
            and block.text[:1] == block.text[:1].lower()
            and result[-1].text[-1] == "-"
            and block.text[0].isalpha()
        ):
            new_text = result[-1].text[:-1] + block.text.strip()
            new_block = replace(block, text=new_text)
            result[-1] = new_block
        else:
            result.append(block)
    return result


def fix_titles(blocks):
    """
    if page contains 3+ headers, all headers except first will be converted to text
    each header could be only once in the document
    :param blocks:
    :return:
    """
    result = []
    seen_headers = set()
    current_page = -1
    page_headers = []

    # First pass - collect headers per page
    for block in blocks:
        if block.page_number != current_page:
            # Process previous page headers if needed
            if len(page_headers) >= 3:
                # Keep only first header
                for header_idx in page_headers[1:]:
                    blocks[header_idx] = replace(blocks[header_idx], block_type="text")
            page_headers = []
            current_page = block.page_number

        if block.block_type in ["title", "sub_title"]:
            page_headers.append(blocks.index(block))

    # Process last page
    if len(page_headers) >= 3:
        for header_idx in page_headers[1:]:
            blocks[header_idx] = replace(blocks[header_idx], block_type="text")

    # Second pass - handle duplicate headers
    for block in blocks:
        if block.block_type in ["title", "sub_title"]:
            if block.text in seen_headers:
                # Convert duplicate header to text
                result.append(replace(block, block_type="text"))
            else:
                seen_headers.add(block.text)
                result.append(block)
        else:
            result.append(block)

    result2 = result[:1]
    for block in result[1:]:
        if (
            result2[-1].block_type in ["title", "sub_title"]
            and block.block_type in ["title", "sub_title", "text"]
            and "\n" not in block.text.strip()
            and block.tokens < 10
        ):
            new_text = result2[-1].text + " " + block.text.strip()
            new_text = new_text.replace("\n", " ")
            result2[-1] = replace(result2[-1], text=new_text)
        elif block.block_type in ["title", "sub_title"]:
            new_text = block.text.strip().replace("\n", " ")
            result2.append(replace(block, text=new_text))
        else:
            result2.append(block)
    return result2


def blocks_to_md_file(blocks, title):
    result = f"# {title}\n\n"
    for block in blocks:
        if block.block_type == "image":
            if block.text.strip():
                result += f"![{block.text}]({block.image_path})\n\n"
            else:
                result += f"![]({block.image_path})\n\n"
        elif block.block_type == "title":
            result += f"# {block.text}\n\n"
        elif block.block_type == "sub_title":
            result += f"## {block.text}\n\n"
        elif block.block_type == "text":
            text = latex_helper.render_latex_in_text(block.text)
            result += f"{text}\n\n"
        elif block.block_type == "equation":
            new_content = block.text.strip().replace(r"\[", "").replace(r"\]", "")
            latex = new_content.strip()
            if len(latex) > 25:
                result += f"![]({block.image_path})\n\n"
                continue
            rendered_mathml = latex_helper.latex_to_mathml(latex)
            if rendered_mathml:
                result += f"{rendered_mathml}\n\n"
            else:
                result += f"![]({block.image_path})\n\n"
        else:
            result += f"{block.text}\n\n"
    file_name = generate_random_filename("blocks_to_md", "md")
    with open(get_abs_path(file_name), "w") as f:
        f.write(result)
    return file_name


def process_pdf_document(pdf_document):
    """Process a PDF document using the pipeline."""
    pipeline = get_pipeline()
    # Add cover image parameter for convert_to_mobi
    pdf_document, _log = fold_pipeline(pipeline, pdf_document)
    return pdf_document


def pdf_to_mobi(file_name):
    """Main function to convert PDF to MOBI using the pipeline approach."""
    last_saved_pipeline_state = get_last_pipeline_state(PDFDocument, {"file_name": file_name})
    if last_saved_pipeline_state and get_config().start_from:
        pdf_document, _ = restart_stage(
            get_config().start_from, get_pipeline(), last_saved_pipeline_state, PDFDocument
        )
        return pdf_document.mobi_file_path
    else:
        pdf_document = PDFDocument(file_name=file_name)
        pdf_document = process_pdf_document(pdf_document)
        return pdf_document.mobi_file_path
