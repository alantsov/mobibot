import urllib

import requests
from bs4 import BeautifulSoup

from src.helpers.filepath_helper import generate_random_filename, get_abs_path


def download_html_page(link, cookies=None):
    html_filename = generate_random_filename("original", "html")
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Referer": urllib.parse.quote(link, safe=":/"),
    }
    response = requests.get(link, headers=headers, cookies=cookies, timeout=60)
    if response.headers.get("Content-Type").startswith("application/pdf"):
        html_filename = generate_random_filename("original", "pdf")
        with open(get_abs_path(html_filename), "wb") as f:
            f.write(response.content)
    else:
        with open(get_abs_path(html_filename), "w") as f:
            response.encoding = "utf-8"
            f.write(response.text)
    return html_filename


def load_html_page_by_url(url: str) -> str or None:
    """
    :param url: link to html page.
    :return: content of html page or None if error occurred.
    """
    try:
        print(f"Downloading page: {url}")
        html_file = download_html_page(url)
        with open(f"data/{html_file}") as f:
            html_content = f.read()
            soap = BeautifulSoup(html_content, "html.parser")
            trash_tags = ["style", "svg", "img", "link[rel=stylesheet]"]
            for trash_tag_name in trash_tags:
                for tag in soap.find_all(trash_tag_name):
                    tag.extract()
            for tag in soap.find_all("script"):
                if tag.has_attr("src"):
                    tag.extract()
                elif tag.has_attr("type") and tag["type"] in [
                    "application/ld+json",
                    "application/json",
                ]:
                    continue
                else:
                    tag.extract()
            with open(f"data/{html_file}_short.html", "w", encoding="utf-8") as f:
                f.write(str(soap))
            result = str(soap)
            result = result[:100000]
            return result
    except Exception as e:
        print(f"Error downloading page: {e}")
        return None
