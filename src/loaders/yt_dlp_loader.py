import json
import logging
import os
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

from src.helpers.filepath_helper import get_rel_path
from src.models.video_models import Chapter
from src.wrappers import docker_wrapper

logger = logging.getLogger(__name__)


def yt_dlp_with_auto_dubbing(video_url):
    suffix = ["-f", "worstvideo+bestaudio[format_note*=original]", video_url]
    return download_video_and_metainfo(video_url, suffix)


def yt_dlp_without_auto_dubbing(video_url):
    suffix = ["-f", "worstvideo+bestaudio", video_url]
    return download_video_and_metainfo(video_url, suffix)


def yt_dlp_no_recode(video_url):
    suffix = [video_url]
    return download_video_and_metainfo(video_url, suffix)


def yt_dlp_recode(video_url):
    suffix = [video_url, "--recode", "mkv"]
    return download_video_and_metainfo(video_url, suffix)


def download_video_and_metainfo(video_url, suffix):
    # Ensure downloads directory exists
    downloads_dir = "data/downloads"
    os.makedirs(downloads_dir, exist_ok=True)

    # Create download archive file if it doesn't exist
    archive_file = os.path.join(downloads_dir, "download_archive.txt")
    if not os.path.exists(archive_file):
        open(archive_file, "a").close()

    # Extract video ID
    video_url, video_id = extract_video_id(video_url)

    # Create video-specific directory
    video_dir = os.path.join(downloads_dir, video_id)
    os.makedirs(video_dir, exist_ok=True)

    # Set output template using video ID
    filename = "%(id)s.%(ext)s"
    archive_file_cont = get_rel_path(archive_file)
    video_dir_cont = get_rel_path(video_dir)

    base_command = [
        "--write-info-json",
        "--download-archive",
        archive_file_cont,
        "-o",
        f"{video_dir_cont}/{filename}",
        "--sponsorblock-remove",
        "all",
    ]

    command = base_command + suffix
    result = docker_wrapper.run_docker_container("yt_dlp", command)
    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp failed with error: {result.stderr}")

    # Find the downloaded files
    json_filename = ""
    video_filename = ""
    files_in_dir = [f for f in os.listdir(video_dir)]
    for file in files_in_dir:
        if file.endswith(".json"):
            json_filename = os.path.join(video_dir, file)
        elif not file.endswith(".part"):  # Ignore partial downloads
            video_filename = os.path.join("downloads", video_id, file)
    with open(json_filename) as f:
        parsed_json = json.load(f)
    title = parsed_json["title"] if "title" in parsed_json else ""
    author = parsed_json["creator"] if "creator" in parsed_json else ""
    if not author:
        author = parsed_json["channel"] if "channel" in parsed_json else ""
    if not author:
        author = parsed_json["uploader"] if "uploader" in parsed_json else ""
    if not author:
        try:
            soup = BeautifulSoup(requests.get(video_url).text, "html.parser")
            json_oembed_link = soup.find("link", rel="alternate", type="application/json+oembed")[
                "href"
            ]
            json_oembed = requests.get(json_oembed_link).json()
            author = json_oembed["author_name"]
        except Exception as e:
            logger.debug(f"Error: {e}")
    description = parsed_json["description"] if "description" in parsed_json else ""
    language = parsed_json["language"] if "language" in parsed_json else "en"
    chapters = []
    if "chapters" in parsed_json:
        chapters = [
            Chapter(ch["title"], ch["start_time"], ch.get("end_time", 0) - ch["start_time"])
            for ch in parsed_json["chapters"]
        ]
    sponsor_segments = (
        parsed_json["sponsorblock_chapters"] if "sponsorblock_chapters" in parsed_json else []
    )
    for sponsor in sponsor_segments:
        logger.debug("sponsor %s %s", sponsor["start_time"], sponsor["end_time"])
    logger.debug("chapters %s", chapters)
    chapters = shift_chapters_by_sponsors(chapters, sponsor_segments)
    logger.debug("chapters %s", chapters)
    # sponsor_segment example {"start_time": 599.85, "end_time": 713.526, "category": "sponsor", "title": "Sponsor"}
    return video_filename, title, description, author, chapters, sponsor_segments, language


def shift_chapters_by_sponsors(chapters: list[Chapter], sponsor_segments) -> list[Chapter]:
    """Adjust chapters based on sponsor segments in the video.

    Args:
        chapters: List of Chapter objects containing start time and duration
        sponsor_segments: List of sponsor segment dictionaries with start_time and end_time

    Returns:
        List of Chapter objects with adjusted timings accounting for sponsor segments

    Rules:
        - Chapters fully inside sponsor segments are removed
        - Chapters intersecting sponsor segments are trimmed
        - Chapters after sponsor segments are shifted by sponsor duration
    """
    if not sponsor_segments:
        return chapters
    if not chapters:
        return []

    def merge_overlapping_segments(segments):
        if not segments:
            return []
        sorted_segments = sorted(segments, key=lambda x: x["start_time"])
        merged = [sorted_segments[0]]
        for segment in sorted_segments[1:]:
            if segment["start_time"] <= merged[-1]["end_time"]:
                merged[-1]["end_time"] = max(merged[-1]["end_time"], segment["end_time"])
            else:
                merged.append(segment)
        return merged

    def is_inside_sponsor(chapter: Chapter, sponsor):
        return (
            chapter.start_seconds >= sponsor["start_time"]
            and chapter.start_seconds + chapter.duration <= sponsor["end_time"]
        )

    def intersects_sponsor(chapter: Chapter, sponsor):
        chapter_end = chapter.start_seconds + chapter.duration
        return chapter.start_seconds <= sponsor["end_time"] and chapter_end >= sponsor["start_time"]

    result_chapters = []
    total_sponsor_duration = 0

    # Merge overlapping sponsor segments
    sponsor_segments = merge_overlapping_segments(sponsor_segments)

    for chapter in chapters:
        skip_chapter = False
        adjusted_start = chapter.start_seconds
        adjusted_duration = chapter.duration

        for sponsor in sponsor_segments:
            # Skip if chapter is fully inside sponsor
            if is_inside_sponsor(chapter, sponsor):
                skip_chapter = True
                break

            # Adjust chapter if it intersects sponsor
            if intersects_sponsor(chapter, sponsor):
                sponsor_duration = sponsor["end_time"] - sponsor["start_time"]

                if chapter.start_seconds < sponsor["start_time"]:
                    # Chapter starts before sponsor
                    adjusted_duration -= min(
                        adjusted_duration,
                        sponsor_duration
                        + (chapter.start_seconds + chapter.duration - sponsor["end_time"]),
                    )
                else:
                    # Chapter starts inside sponsor
                    sponsor_duration = sponsor["end_time"] - sponsor["start_time"]
                    sponsor_overlap = sponsor["end_time"] - chapter.start_seconds
                    adjusted_start += sponsor_overlap
                    adjusted_duration -= sponsor_overlap
                    adjusted_start -= sponsor_duration

            # Shift chapter if sponsor is before it
            elif sponsor["end_time"] <= chapter.start_seconds:
                sponsor_duration = sponsor["end_time"] - sponsor["start_time"]
                total_sponsor_duration += sponsor_duration
                adjusted_start -= sponsor_duration

        if not skip_chapter and adjusted_duration > 1:
            result_chapters.append(Chapter(chapter.title, adjusted_start, adjusted_duration))

    return result_chapters


def extract_video_id(video_url):
    """Extract video ID from various YouTube URL formats."""
    # Clean the URL by removing unnecessary parameters
    parsed_url = urlparse(video_url)
    query_params = parse_qs(parsed_url.query)
    if "si" in query_params:
        del query_params["si"]
    clean_url = urlunparse(parsed_url._replace(query=urlencode(query_params, doseq=True)))

    # Try to get video ID from different URL formats
    parsed_url = urlparse(clean_url)
    video_id = None

    # Try query parameters
    video_id = parse_qs(parsed_url.query).get("v", [None])[0]

    # Try shortened URL format
    if not video_id and "youtu.be" in parsed_url.netloc:
        video_id = parsed_url.path.strip("/")

    # Try /watch/ path format
    if not video_id and "/watch/" in parsed_url.path:
        video_id = parsed_url.path.split("/watch/")[-1]

    # Use yt-dlp as a fallback
    if not video_id:
        try:
            command = ["--get-id", clean_url]
            result = docker_wrapper.run_docker_container("yt_dlp", command)
            if result.returncode != 0:
                raise RuntimeError(f"yt-dlp failed to get video ID: {result.stderr}")
            video_id = result.stdout.strip()
        except Exception:
            return video_url, str(hash(video_url))
    return clean_url, video_id
