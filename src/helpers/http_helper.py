import hashlib
import logging
import os
from urllib.parse import urlparse, urlunparse

import requests

logger = logging.getLogger(__name__)


def add_https_to_link(url):
    parsed_url = urlparse(url)
    if parsed_url.scheme != "https":
        if not parsed_url.netloc:
            parsed_url = urlparse("//" + url, scheme="https")
        else:
            parsed_url = parsed_url._replace(scheme="https")
    return str(urlunparse(parsed_url))


def download_file(link, ext, timeout=120):
    logger.debug("download file %s", link)
    try:
        filename = f"data/{hashlib.sha256(link.encode('utf-8')).hexdigest()}.{ext}"
        if os.path.exists(filename):
            logger.debug("download file read from cache")
            yield filename
        else:
            file_response = requests.get(link, timeout=timeout)
            file_response.raise_for_status()
            if "Content-Type" in file_response.headers:
                content_type = file_response.headers["Content-Type"].split("/")[-1]
                ext2 = content_type.split(";")[0].strip()
                filename = f"data/{hashlib.sha256(link.encode('utf-8')).hexdigest()}.{ext2}"
            with open(filename, "wb") as f:
                f.write(file_response.content)
            yield filename
    except Exception:
        logger.exception("download_file failed")
        return None
