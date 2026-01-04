import datetime
import os
import subprocess
import traceback

from src.controllers import longread, pdf, video
from src.controllers.video import handle_video_file
from src.helpers import text_helper
from src.helpers.filepath_helper import get_abs_path, get_rel_path

OUTPUT = "output"


def convert_to_mobi(filename, title=None, author=None, cover=None):
    extension = os.path.basename(filename).split(".")[-1]
    filename = get_rel_path(filename)
    try:
        if extension in ["html", "htm"]:
            new_file_name = longread.link2mobi("", filename)
        elif extension in ["pdf", "djvu"]:
            new_file_name = pdf.pdf_to_mobi(filename)
        elif extension in ["mp4", "mkv", "webm"]:
            if not title:
                date = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
                title = f"video_{date}"
            if not author:
                author = "Unknown author"
            new_file_name = handle_video_file(filename, title, author)
        elif extension in ["ogg", "mp3", "wav", "aac", "MP4"]:
            if not title:
                date = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
                title = f"audio_{date}"
            if not author:
                author = "Unknown author"
            new_file_name = video.handle_audio_file(filename, title, author, cover)
        else:
            raise Exception(f"unknown file extension {extension}")
        copy_result_to_output(new_file_name)
        return new_file_name
    except Exception as e:
        print(e)
        print(traceback.format_exc())
        return None


def handle_text_message(text, entities_links=None):
    error_message = None
    file = None
    links = text_helper.extract_links(text)
    if len(links) == 0 and entities_links:
        links = entities_links
    if len(links) > 1:
        if links[0].startswith("https://t.me/"):
            link = links[1]
        else:
            link = links[0]
        try:
            file = handle_single_link(link)
        except Exception:
            print(traceback.format_exc())
            error_message = "something went wrong"
    elif len(links) > 0:
        try:
            file = handle_single_link(links[0])
        except Exception:
            print(traceback.format_exc())
            error_message = "something went wrong"
    else:
        error_message = f"can not handle this text: {text}"
    if file:
        copy_result_to_output(file)
    return file, error_message


def copy_result_to_output(file):
    os.makedirs(OUTPUT, exist_ok=True)
    subprocess.run(["cp", get_abs_path(file), OUTPUT])


def handle_single_link(link):
    if is_playlist(link):
        return video.handle_youtube_playlist_link(link)
    elif is_video(link):
        return video.handle_youtube_video_link(link)
    else:
        return longread.link2mobi(link)


def is_video(link):
    return any(
        [
            link.startswith("https://www.youtube.com/watch"),
            link.startswith("https://youtube.com/watch"),
            link.startswith("https://youtu.be/"),
            link.startswith("https://youtube.com/live/"),
            link.startswith("https://www.youtube.com/live"),
            link.startswith("https://m.youtube.com/watch"),
            link.startswith("https://archive.org/details/"),
            link.startswith("https://cds.cern.ch/record/"),
            link.startswith("https://www.bitchute.com/video/"),
            link.startswith("https://bitchute.com/video/"),
        ]
    )


def is_playlist(link):
    return any(
        [
            link.startswith("https://www.youtube.com/playlist"),
            link.startswith("https://youtube.com/playlist"),
            link.startswith("https://m.youtube.com/playlist"),
        ]
    )
