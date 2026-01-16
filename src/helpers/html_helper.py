import base64
import logging
import urllib
import urllib.parse
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from tqdm import tqdm

from src.helpers.filepath_helper import generate_random_filename, get_abs_path, get_rel_path

from ..wrappers import ollama_wrapper
from ..wrappers.readability_wrapper import readability
from . import http_helper, text_helper
from .latex_helper import process_math

logger = logging.getLogger(__name__)


from src.config import get_config
from src.wrappers.fasttext_wrapper import detect_language


def save_to_html(title, inner_html):
    html_filename = generate_random_filename(text_helper.clean_title(title), "html")
    html_content = f"""<!DOCTYPE html>
            <head>
                <meta charset="UTF-8">
                <title>{title}</title>
            </head>
            <body>
                {inner_html}
            </body>
            </html>"""
    with open(get_abs_path(html_filename), "w") as f:
        f.write(html_content)
    return html_filename


def remove_everything_before(current_element):
    if current_element is None:
        return
    if current_element.name in ["body", "html"]:
        return
    for element in current_element.parent.children:
        if element == "\n":
            continue
        if element != current_element:
            element.extract()
        else:
            break
    remove_everything_before(current_element.parent)


def preprocess_generic_page(input_file, link=""):
    html_filename = get_rel_path(input_file)
    with open(get_abs_path(html_filename)) as f:
        html_content = f.read()
    html_filename_preprocessed = generate_random_filename("preprocessed", "html")
    readability_result = readability(html_content, link)
    html_content_2 = readability_result["content"]
    soup = BeautifulSoup(html_content, "html.parser")
    body = soup.find("body")
    if body:
        body.replace_with(BeautifulSoup(f"<body>{html_content_2}</body>", "html.parser"))
        html_content3 = str(soup)
    else:
        html_content3 = f"<head></head><body>{html_content_2}</body>"
    with open(get_abs_path(html_filename_preprocessed), "w") as f:
        f.write(html_content3)
    return html_filename_preprocessed, readability_result["title"], readability_result.get("byline")


def preprocess_html(soup, link):
    """Performs initial HTML cleanup and preprocessing"""
    if soup.body.find("h1") and link.startswith("https://arxiv.org"):
        remove_everything_before(soup.body.find("h1"))

    # Remove unwanted elements
    garbage = [
        "footer",
        "header",
        "nav",
        "object",
        "iframe",
        "audio",
        "style",
        "svg",
        "form",
        "select",
        "button",
        "dialog",
    ]

    for center_tag in soup.find_all("center"):
        center_tag.replace_with_children()
    for trash in garbage:
        for trash_el in soup.find_all(trash):
            trash_el.extract()

    # Clean up scripts
    for script_el in soup.find_all("script"):
        if script_el.has_attr("type") and script_el["type"] == "application/ld+json":
            continue
        else:
            script_el.extract()

    # Remove other unwanted elements
    for trash_el in soup.find_all(class_="not-prose"):
        trash_el.extract()
    for trash_el in soup.select("a svg"):
        trash_el.extract()
    for trash_el in soup.select('div[class*="modal"]'):
        trash_el.extract()
    for trash_el in soup.select('div[class*="menu"]'):
        trash_el.extract()
    for trash_el in soup.select("head link"):
        trash_el.replace_with_children()

    # Clean up formatting tags
    for u_tag in soup.find_all("u"):
        u_tag.replace_with_children()

    # Handle background images in links
    for a_tag in soup.select('a[style*="background-image"]'):
        style = a_tag["style"]
        rules = style.split(";")
        for rule in rules:
            if "background-image" in rule:
                image_url = ":".join(rule.split(":")[1:])
                image_url = image_url.strip()
                image_url = image_url[4:][:-1]
                image_url = image_url.strip()
                image_url = image_url[1:][:-1]
                new_tag = BeautifulSoup(f'<img src="{image_url}">', "html.parser")
                a_tag.replace_with(new_tag)
                break

    # Clean up links and headers
    for a_tag in soup.find_all("a"):
        a_tag.replace_with_children()
    for header_tag_name in ["h5", "h6"]:
        for h6_tag in soup.find_all(header_tag_name):
            if h6_tag.get_text(strip=True).lower()[:8] in ["abstract", "acknowle"]:
                new_tag = BeautifulSoup(f"<h2>{h6_tag.get_text(strip=True)}</h2>", "html.parser")
                h6_tag.replace_with(new_tag)

    # Clean up list items
    for li_p_tag in soup.select("li p"):
        li_p_tag.replace_with_children()
    for li_p_tag in soup.select("li div"):
        li_p_tag.replace_with_children()
    for li_tag in soup.find_all("li"):
        for br in li_tag.find_all(text="\n"):
            br.extract()
    for li_span_tag in soup.select("li span"):
        parent = li_span_tag.parent
        first_child = parent.contents[0] if parent else None
        is_first_child = li_span_tag == first_child
        if li_span_tag.get_text(strip=True) in "●○■□◆◇▪▫•" and is_first_child:
            li_span_tag.extract()

    # Clean up attributes
    for any_element in soup.body.find_all():
        if "svg" in [
            cur_parent.name for cur_parent in ([any_element] + any_element.find_parents())
        ]:
            for attr_key in list(any_element.attrs):
                if attr_key in ["xmlns:inkscape", "xmlns:sodipodi"]:
                    del any_element.attrs[attr_key]
            continue
        for attr_key in list(any_element.attrs):
            if attr_key in ["class", "style"] or attr_key.startswith("data"):
                if attr_key == "data-src" and any_element.name == "img":
                    any_element["src"] = any_element["data-src"]
                del any_element.attrs[attr_key]

    # Final cleanup
    for trash_el in soup.select("head meta"):
        trash_el.extract()
    for trash_el in soup.select("svg style"):
        trash_el.extract()
    for trash_el in soup.select("svg defs"):
        trash_el.extract()
    for trash_el in soup.select("svg *"):
        if trash_el.name == "sodipodi:namedview":
            trash_el.extract()

    return soup


def process_images(soup, link):
    """Process and download images"""
    img_tags = soup.find_all("img")

    for i, img_tag in tqdm(enumerate(img_tags), desc="Downloading images"):
        if not img_tag.has_attr("src"):
            if img_tag.parent.name == "picture":
                source_tags = img_tag.parent.find_all("source")
                if len(source_tags) > 0:
                    source_tag = source_tags[0]
                    img_tag.attrs["src"] = source_tag["srcset"].split(" ")[0]
            if not img_tag.has_attr("src"):
                img_tag.extract()
                continue

        image_url = img_tag["src"]
        if image_url.startswith("data"):
            try:
                mime_type, image_data = image_url.split(";base64,")
                image_ext = mime_type.split("/")[-1]
                image_file_name = generate_random_filename("image", image_ext)
                image_data = base64.b64decode(image_data)
                with open(get_abs_path(image_file_name), "wb") as img_file:
                    img_file.write(image_data)
                img_tag["src"] = image_file_name
            except Exception as e:
                logger.debug(f"Failed to process data URL: {e}")
                img_tag.extract()
        else:
            image_ext = image_url.split(".")[-1]
            if image_ext.lower() in ["png", "jpeg", "jpg"]:
                parsed_image_url = urllib.parse.urlparse(image_url)
                if not all([parsed_image_url.scheme, parsed_image_url.netloc]):
                    url = link
                    base_tag = soup.find("base")
                    if base_tag and base_tag.has_attr("href"):
                        base_url = urljoin(url, base_tag["href"])
                    else:
                        base_url = url
                    image_url = urljoin(base_url, image_url)
                    if image_url.startswith("https://web.archive.org/web/"):
                        image_url = "/".join(image_url.split("/")[5:])
                for image_file_name_i in http_helper.download_file(
                    image_url, image_ext, timeout=10
                ):
                    img_tag["src"] = image_file_name_i.split("/")[1]
            else:
                img_tag.extract()
    for trash_el in soup.select("head base"):
        trash_el.extract()
    return soup


def translate_p_tags(soup):
    if not get_config().translate_to:
        return soup
    text = soup.get_text(strip=True)

    if not text:
        return soup
    language = detect_language(text)
    if language == get_config().translate_to:
        return soup
    if language is None:
        return soup
    tags_names_to_translate = ["h1", "h2", "h3", "h4", "h5", "h6", "p", "li"]
    tags_to_translate = [
        tag for tag_name in tags_names_to_translate for tag in soup.find_all(tag_name)
    ]
    for p_tag in tqdm(tags_to_translate, desc="Translating text in html tags"):
        if p_tag.get_text(strip=True) == "":
            continue
        tag_text = p_tag.get_text(strip=True)
        new_text = ollama_wrapper.translate(tag_text, language, get_config().translate_to)
        if new_text:
            new_tag = BeautifulSoup(f"<{p_tag.name}>{new_text}</{p_tag.name}>", "html.parser")
            p_tag.replace_with(new_tag)
        else:
            continue
    return soup


def _apply_transformation_to_html(input_file, transform_func, prefix, **kwargs):
    html_filename = get_rel_path(input_file)
    output_filename = generate_random_filename(prefix, "html")

    with open(get_abs_path(html_filename)) as f:
        soup = BeautifulSoup(f, "html.parser")

    soup = transform_func(soup, **kwargs)

    with open(get_abs_path(output_filename), "w") as f:
        f.write(str(soup))
    return output_filename


def translate_html_file(input_file):
    return _apply_transformation_to_html(input_file, translate_p_tags, "translated")


def initial_html_clean_up(input_file, link=""):
    return _apply_transformation_to_html(input_file, preprocess_html, "cleaned", link=link)


def render_latex(input_file):
    return _apply_transformation_to_html(input_file, process_math, "latex")


def localize_images(input_file, link=""):
    return _apply_transformation_to_html(input_file, process_images, "localized", link=link)


def extract_cover_from_html(html_filename):
    with open(get_abs_path(html_filename)) as f:
        html_content = f.read()
    soup = BeautifulSoup(html_content, "html.parser")
    for img in soup.select("img"):
        if "src" in img.attrs and img["src"]:
            return img["src"]
    return None


def html_to_text(html_filename):
    with open(get_abs_path(html_filename)) as f:
        html_content = f.read()
    soup = BeautifulSoup(html_content, "html.parser")
    text = ""
    for tag in soup.find_all():
        if tag.name in ["p"]:
            parents_name =  list(map(lambda t: t.name, tag.parents))
            if 'figcaption' in parents_name or 'figure' in parents_name:
                continue
            text += tag.get_text(strip=True) + "\n"
    text_filename = generate_random_filename("text_from_html", "txt")
    with open(get_abs_path(text_filename), "w") as f:
        f.write(text)
    return text_filename
