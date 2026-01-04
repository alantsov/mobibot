import uuid

import requests
from bs4 import BeautifulSoup

READABILITY_PORT = 8080


def set_readability_port(port):
    global READABILITY_PORT
    READABILITY_PORT = port


def readability(html_content, link):
    soup = BeautifulSoup(html_content, "html.parser")
    for script in soup(["script", "style"]):
        script.extract()
    images_dict = {}
    for img in soup.find_all("img"):
        img_src = img.get("src")
        img_uuid = f"{uuid.uuid4()}"
        images_dict[img_uuid] = img_src
        img["src"] = img_uuid
        img["data-src-uuid"] = img_uuid
    params = {"url": link, "html": str(soup)}
    base_url = f"http://127.0.0.1:{READABILITY_PORT}"
    result = requests.get(base_url, data=params)
    result.raise_for_status()
    result_json = result.json()
    readable_html_content = result_json["content"]
    soup = BeautifulSoup(readable_html_content, "html.parser")
    for img in soup.find_all("img"):
        img_uuid = img.get("data-src-uuid")
        img["src"] = images_dict[img_uuid]
    result_json["content"] = str(soup)

    return result_json
