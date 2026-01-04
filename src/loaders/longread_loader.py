import os
from urllib.parse import parse_qs, urlencode, urlparse

import requests
from bs4 import BeautifulSoup

from src.helpers import markdown_helper
from src.helpers.filepath_helper import generate_random_filename, get_abs_path
from src.helpers.http_helper import add_https_to_link
from src.loaders.html_loader import download_html_page
from src.pipeline import one_of
from src.wrappers import readability_wrapper


def download_longread(url):
    loaders = [
        simple_download,
        download_html_page,
        arxiv_pdf_download,
        google_drive_download,
        archive_ph_download,
        archive_org_download,
        google_doc_download,
        r_jina_ai_download,
    ]
    return one_of(loaders, url, check_downloaded_page)


def simple_download(url):
    response = requests.get(url)
    response.raise_for_status()
    filename = generate_random_filename("simple", "html")
    with open(get_abs_path(filename), "w", encoding="utf-8") as file:
        file.write(response.text)
    return filename


def arxiv_pdf_download(url):
    if not url.startswith("https://arxiv.org/html/"):
        return None
    download_url = url.replace("https://arxiv.org/html/", "https://arxiv.org/pdf/")
    pdf_content = requests.get(download_url).content
    pdf_filename = generate_random_filename("arxiv", "pdf")
    with open(get_abs_path(pdf_filename), "wb") as f:
        f.write(pdf_content)
    return pdf_filename


def archive_org_download(url):
    parsed_url_for_wayback = urlparse(add_https_to_link(url))
    link_for_wayback = (
        parsed_url_for_wayback.scheme
        + "://"
        + parsed_url_for_wayback.netloc
        + parsed_url_for_wayback.path
    )
    # GET
    # 	https://web.archive.org/__wb/sparkline?output=json&url=https://habr.com/ru/articles/838682/&collection=web
    archive_base_url = "https://web.archive.org/__wb/sparkline?"
    archive_params = {"url": link_for_wayback, "collection": "web", "output": "json"}
    archive_full_url = archive_base_url + urlencode(archive_params)
    archive_response = requests.get(
        archive_full_url, headers={"Referer": f"https://web.archive.org/web/20240000000000*/{url}"}
    )
    archive_response.raise_for_status()
    timestamp_for_link = archive_response.json()["last_ts"]
    link3 = f"https://web.archive.org/web/{timestamp_for_link}/{url}"
    filename = simple_download(link3)
    return filename


def archive_ph_download(url):
    list_link = "https://archive.ph/" + url
    response = requests.get(list_link, allow_redirects=False)
    soup = BeautifulSoup(response.content, "html.parser")
    links = soup.find_all("a")
    result_link = None
    for link in links:
        if (
            link.get("href")
            and link.get("href").startswith("https://archive.ph/")
            and len(link.get("href")) <= len("https://archive.ph/") + 6
        ):
            result_link = link.get("href")
    if not result_link:
        raise Exception(url + "not found on archive.ph")
    response = requests.get(result_link, allow_redirects=False)
    filename = generate_random_filename("archive_ph", "html")
    with open(get_abs_path(filename), "w", encoding="utf-8") as file:
        file.write(response.text)
    return filename


def google_doc_download(url):
    if not url.startswith("https://docs.google.com/document/"):
        raise Exception(url + " not google doc")
    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)
    if "docid" in query_params:
        doc_id = query_params["docid"][0]
    else:
        # /document/d/docid
        doc_id = parsed_url.path.split("/")[3]
    doc_url = f"https://docs.google.com/document/d/{doc_id}/export?format=html"
    response = requests.get(doc_url, headers={"Referer": url})
    response.raise_for_status()
    filename = generate_random_filename("google_doc", "html")
    with open(get_abs_path(filename), "w", encoding="utf-8") as file:
        file.write(response.text)
    return filename


def google_drive_download(url):
    if url.startswith("https://drive.google.com/file/d/"):
        file_id = url.split("/")[-2]
        url = f"https://drive.google.com/uc?id={file_id}&export=download"
        response = requests.get(url, headers={"Referer": url})
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "")
        ext = content_type.split("/")[-1]
        if ext == "octet-stream":
            magic_numbers = {
                b"%PDF": "pdf",
                b"PK\x03\x04": "epub",
                b"\x89PNG": "png",
                b"\xff\xd8\xff": "jpg",
                b"GIF8": "gif",
                b"<?xml": "xml",
                b"\xef\xbb\xbf": "txt",
                b"\xff\xfe": "txt",
                b"\xfe\xff": "txt",
                b"ID3": "mp3",
                b"OggS": "ogg",
            }
            content_start = response.content[:10]
            for magic, extension in magic_numbers.items():
                if content_start.startswith(magic):
                    ext = extension
                    break
            if ext == "octet-stream":
                ext = "bin"
        filename = generate_random_filename("google_drive", ext)
        with open(get_abs_path(filename), "wb") as file:
            file.write(response.content)
        return filename
    else:
        raise Exception(url + " not google drive")


def r_jina_ai_download(url):
    r_jina_ai_url = f"https://r.jina.ai/{url}"
    filename = simple_download(r_jina_ai_url)
    with open(get_abs_path(filename), encoding="utf-8") as f:
        md_text = f.read()
    md_filename = generate_random_filename("r_jina_ai", "md")
    with open(get_abs_path(md_filename), "w", encoding="utf-8") as file:
        file.write(md_text)
    html_file_name = markdown_helper.markdown_to_html(md_filename)
    return html_file_name


def is_pdf_file(filename):
    try:
        with open(get_abs_path(filename), "rb") as f:
            header = f.read(4)
            return header == b"%PDF" and filename.endswith(".pdf")
    except Exception:
        return False


def check_downloaded_page(filename, link):
    if not filename:
        raise Exception("not downloaded")
    if not os.path.exists(get_abs_path(filename)):
        raise Exception("not downloaded")
    if os.path.getsize(get_abs_path(filename)) < 1000:
        raise Exception("too small file")

    if is_pdf_file(filename):
        return True

    with open(get_abs_path(filename), encoding="utf-8") as f:
        html_content = f.read()
    readability_result = readability_wrapper.readability(html_content, link)
    html_content_2 = readability_result["content"]
    soup = BeautifulSoup(html_content, "html.parser")
    soup2 = BeautifulSoup(html_content_2, "html.parser")
    for script in soup(["script", "style"]):
        script.extract()
    readable_html_content = soup.get_text().replace("\n", "").replace("\t", "").replace("  ", "")
    for script in soup2(["script", "style"]):
        script.extract()
    readable_html_content2 = soup2.get_text().replace("\n", "").replace("\t", "").replace("  ", "")
    if len(readable_html_content) < 1000:
        raise Exception("too small file")
    if len(readable_html_content2) < 1000:
        raise Exception("too small file")
    return True
