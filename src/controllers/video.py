import json
import logging
import os
import random
from dataclasses import dataclass

from tqdm import tqdm

import src.helpers.html_helper as html_helper
import src.helpers.text_helper as text_helper
import src.wrappers.ollama_wrapper as ollama_wrapper
import src.wrappers.whisperx_wrapper
from src.config import get_config
from src.helpers.filepath_helper import generate_random_filename, get_abs_path, get_rel_path
from src.helpers.grammar_helper import fix_grammar_with_llm
from src.loaders import media_loader
from src.models.video_models import Chapter
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
    clip_select_wrapper,
    docker_wrapper,
    language_tool_wrapper,
    pillow_wrapper,
    pymorphy3_wrapper,
    wespeaker_wrapper,
)
from src.wrappers.docker_wrapper import ManagedDockerService, NoManagedService
from src.wrappers.ffmpeg_wrapper import (
    _probe_audio_codec,
    _probe_duration_seconds,
    _run_in_ffmpeg_container,
)
from src.wrappers.ollama_wrapper import generate_title

logger = logging.getLogger(__name__)

# Resource definitions for PipelineStage
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

LT_RES = PipelineResource(
    factory=lambda: ManagedDockerService("languagetool"),
    setup=lambda service: language_tool_wrapper.set_language_tool_port(service.port),
)


@dataclass
class Video:
    video_url: str
    title: str | None = None
    author: str | None = None
    description: str | None = None
    chapters: list[Chapter] | None = None
    sponsor_segments: list | None = None
    speakers: list | None = None
    unique_speakers: list | None = None
    video_file_name_without_ads: str | None = None
    images_dir: str | None = None
    images_count: int | None = None
    duration_in_seconds: int | None = None
    selected_images: list | None = None
    images_with_seconds: list | None = None
    text_from_selected_images: str | None = None
    whisper_prompt: str | None = None
    dlp_language: str | None = None
    language: str | None = None
    audio_filename: str | None = None
    json_transcript_filename: str | None = None
    json_diarization_filename: str | None = None
    sentence_segments: list | None = None
    sentence_segments_joined: list | None = None
    sentence_segments_joined_simplified: list | None = None
    sentence_segments_with_timings: list | None = None
    sentence_segments_with_speakers: list | None = None
    final_chapters: list[Chapter] | None = (
        None  # Chapter dataclass, chapters or llm generated subtitles
    )
    model: list | None = None  # [h1, h2, p, img]
    joined_model: list | None = None
    processed_model: list | None = None  # [h1, h2, p, img] fixed errors, rejoin p
    translated_model: list | None = None
    cover_filename: str | None = None
    html_filename: str | None = None
    translated_html_filename: str | None = None
    output_filename: str | None = None
    prepared_cover: str | None = None
    cwd: str | None = "data"
    mobi_filename: str | None = None


def handle_audio_file(audio_filename, title, author, cover):
    title = title.replace("\n", "")
    video = Video(
        "",
        duration_in_seconds=0,
        title=title,
        author=author,
        audio_filename=get_rel_path(audio_filename),
    )
    video.language = "ru"
    video.chapters = []
    video.sponsor_segments = []
    video.images_count = 0
    video.selected_images = []
    video.images_with_seconds = []
    if cover:
        video.cover_filename = get_rel_path(cover)
    video = process_video_object(video)
    return video.mobi_filename

def handle_video_file(video_filename, title, author):
    video = Video(
        "",
        video_file_name_without_ads=get_rel_path(video_filename),
        title=title,
        author=author,
        language="ru"
    )
    video = process_video_object(video)
    return video.mobi_filename

def handle_youtube_playlist_link(playlist_url):
    # Create a temporary directory for playlist info
    downloads_dir = "data/downloads"
    os.makedirs(downloads_dir, exist_ok=True)

    # Get playlist metadata
    playlist_command = ["--dump-single-json", playlist_url]
    playlist_result = docker_wrapper.run_docker_container("yt_dlp", playlist_command)
    if playlist_result.returncode != 0:
        raise RuntimeError(f"yt-dlp failed to get playlist metadata: {playlist_result.stderr}")
    playlist_data = json.loads(playlist_result.stdout)

    playlist_title = playlist_data.get("title", "Untitled Playlist")
    playlist_author = playlist_data.get("uploader", "Unknown Author")

    # Get playlist info using yt-dlp
    command = ["--dump-json", "--flat-playlist", playlist_url]

    result = docker_wrapper.run_docker_container("yt_dlp", command)
    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp failed to get flat playlist info: {result.stderr}")
    videos_info = [json.loads(line) for line in result.stdout.splitlines()]

    # Sort videos by upload date
    videos_info.sort(key=lambda x: x.get("upload_date", "00000000"))

    # Process each video
    videos = []
    for video_info in videos_info:
        video_url = f"https://www.youtube.com/watch?v={video_info['id']}"
        video_url = video_info["url"] if "url" in video_info else video_url
        video = process_video_object(Video(video_url))
        videos.append(video)

    # Combine all videos into one model
    model = []
    cover_filename = None
    for video in videos:
        model += video.processed_model
        if cover_filename is None:
            cover_filename = video.cover_filename

    html_file = model_to_html(model, playlist_title)
    output_filename = text_helper.clean_title(playlist_title) + ".mobi"
    try:
        prepared_cover = pillow_wrapper.create_cover(
            cover_filename or "/dev/null", playlist_title, playlist_author, cwd="data"
        )
    except Exception:
        prepared_cover = pillow_wrapper.create_cover(
            "/dev/null", playlist_title, playlist_author, cwd="data"
        )
    mobi_file = calibre_wrapper.convert_book(
        html_file,
        output_filename,
        cwd="data",
        cover=prepared_cover,
        title=playlist_title,
        author=playlist_author,
    )
    return mobi_file


def handle_youtube_video_link(video_url):
    last_saved_pipeline_state = get_last_pipeline_state(Video, {"video_url": video_url})
    if last_saved_pipeline_state and get_config().start_from:
        video, _new_pipeline_state = restart_stage(
            get_config().start_from, get_pipeline(), last_saved_pipeline_state, Video
        )
        return video.mobi_filename
    else:
        video = Video(video_url)
        video = process_video_object(video)
        return video.mobi_filename


def extract_speakers_names(a, b, c, d):
    return ollama_wrapper.extract_speakers_names(a, b, c, d)


def get_pipeline():
    cfg = get_config()
    return [
        PipelineStage(
            media_loader.load_media,
            ["video_url"],
            [
                "video_file_name_without_ads",
                "title",
                "description",
                "author",
                "chapters",
                "sponsor_segments",
                "dlp_language",
            ],
            critical=True,
        ),
        PipelineStage(
            split_video,
            ["video_file_name_without_ads"],
            ["audio_filename", "images_dir", "duration_in_seconds"],
            critical=True,
        ),
        PipelineStage(
            guess_language, ["title", "description", "author", "dlp_language"], ["language"]
        ),
        PipelineStage(
            clip_select_wrapper.select_screenshots_by_CLIP_model,
            ["images_dir"],
            ["selected_images", "images_count"],
        ),
        PipelineStage(
            add_seconds_to_images,
            ["selected_images", "images_count", "duration_in_seconds"],
            ["images_with_seconds"],
        ),
        # Whisper Prompt Generation (Conditional)
        PipelineStage(
            extract_text_from_images,
            ["images_dir", "selected_images"],
            ["text_from_selected_images"],
            enabled=cfg.use_whisper_prompt,
            resources=[OLLAMA_RES],
        ),
        PipelineStage(
            extract_speakers_names,
            ["text_from_selected_images", "title", "author", "description"],
            ["speakers"],
            enabled=cfg.use_whisper_prompt,
            resources=[OLLAMA_RES],
        ),
        PipelineStage(
            deduplicate_speakers,
            ["speakers", "language"],
            ["unique_speakers"],
            enabled=cfg.use_whisper_prompt,
        ),
        PipelineStage(
            generate_whisper_prompt,
            ["title", "description", "unique_speakers", "text_from_selected_images", "language"],
            ["whisper_prompt"],
            enabled=cfg.use_whisper_prompt,
            resources=[OLLAMA_RES],
        ),
        # Transcription & Diarization
        PipelineStage(
            wespeaker_wrapper.diarize,
            ["audio_filename", "language"],
            ["json_diarization_filename"],
            enabled=cfg.diarize,
        ),
        PipelineStage(
            src.wrappers.whisperx_wrapper.audio_to_json,
            ["audio_filename", "language", "whisper_prompt"],
            ["json_transcript_filename"],
            critical=True,
        ),
        PipelineStage(
            join_transcription_and_diarization,
            ["json_transcript_filename", "json_diarization_filename"],
            ["sentence_segments"],
            critical=True,
        ),
        PipelineStage(
            simplify_sentences,
            ["sentence_segments"],
            ["sentence_segments_joined_simplified"],
            resources=[OLLAMA_RES],
            enabled=get_config().simplify_transcript,
        ),
        PipelineStage(
            copy_arguments,
            ["sentence_segments"],
            ["sentence_segments_joined_simplified"],
            enabled=(not get_config().simplify_transcript),
            _given_name="simplify_sentences",
        ),
        # Speaker Matching (Conditional)
        PipelineStage(
            match_speakers,
            ["sentence_segments_joined_simplified", "title", "description", "author"],
            ["sentence_segments_with_speakers"],
            enabled=cfg.diarize,
            resources=[OLLAMA_RES],
        ),
        PipelineStage(
            copy_arguments,
            ["sentence_segments_joined_simplified"],
            ["sentence_segments_with_speakers"],
            enabled=not cfg.diarize,
            _given_name="match_speakers",
        ),
        # Model Creation & Processing
        PipelineStage(
            generate_final_chapters,
            [
                "chapters",
                "sentence_segments_with_speakers",
                "images_with_seconds",
                "language",
                "duration_in_seconds",
                "title",
            ],
            ["final_chapters"],
            resources=[OLLAMA_RES],
        ),
        PipelineStage(
            create_initial_model,
            [
                "title",
                "final_chapters",
                "sentence_segments_with_speakers",
                "images_with_seconds",
                "images_dir",
            ],
            ["model"],
        ),
        PipelineStage(join_paragraphs,
                      ["model"],
                      ["joined_model"]),
        PipelineStage(
            process_model,
            ["joined_model", "language"],
            ["processed_model"],
            resources=[OLLAMA_RES, LT_RES],
            enabled=get_config().fix_grammar,
        ),
        PipelineStage(
            copy_arguments,
            ["joined_model"],
            ["processed_model"],
            enabled=not get_config().fix_grammar,
            _given_name="process_model",
        ),
        PipelineStage(translate_model,
                      ["processed_model", "language"],
                      ["translated_model"],
                      resources=[OLLAMA_RES],
                      enabled=get_config().translate_to is not None),
        PipelineStage(
            copy_arguments,
            ["processed_model"],
            ["translated_model"],
            enabled=get_config().translate_to is None,
            _given_name="translate_model",
        ),
        # Output Generation
        PipelineStage(
            select_cover, ["images_dir", "selected_images", "video_url"], ["cover_filename"]
        ),
        PipelineStage(model_to_html, ["translated_model", "title"], ["html_filename"]),
        PipelineStage(create_output_filename, ["title"], ["output_filename"]),
        PipelineStage(
            pillow_wrapper.create_cover,
            ["cover_filename", "title", "author", "cwd"],
            ["prepared_cover"],
        ),
        PipelineStage(
            calibre_wrapper.convert_book,
            [
                "html_filename",
                "output_filename",
                "cwd",
                "prepared_cover",
                "author",
                "title",
            ],
            ["mobi_filename"],
        ),
    ]


def process_video_object(video):
    pipeline = get_pipeline()
    video, _log = fold_pipeline(pipeline, video)
    return video


def guess_language(text1, text2, text3, dlp_language):
    if dlp_language:
        return dlp_language
    text = ""
    if text1:
        text += text1
    if text2:
        text += text2
    if text3:
        text += text3
    if text:
        detected_language = text_helper.detect_language(text)
        detected_language = "ru" if detected_language == "ru" else "en"
    else:
        detected_language = dlp_language
    logger.debug(f"language: {detected_language}")
    return detected_language


def extract_text_from_images(images_dir, images):
    text = ""
    for image in images:
        filename = images_dir + "/" + image
        image_text = ollama_wrapper.extract_text_from_screenshot(filename)
        if image_text:
            text += " " + image_text
        logger.debug("%s %s", image, image_text)
    return text


def deduplicate_speakers(speakers, language):
    speakers = list(set(speakers))
    final_speakers = []
    for i, speaker in enumerate(speakers):
        if " " not in speaker.strip():
            base_names = pymorphy3_wrapper.extract_base_names(speaker, language)
            include_speaker = True
            for base_name in base_names:
                for name in speakers:
                    if name != speaker:
                        if base_name in name:
                            include_speaker = False
            if include_speaker:
                final_speakers.append(speaker)
        else:
            final_speakers.append(speaker)
    return final_speakers


def generate_whisper_prompt(title, description, speakers, text_from_images, language):
    terms = []
    try:
        terms = ollama_wrapper.extract_terms(text_from_images, description, title)
        terms = ollama_wrapper.filter_terms(terms)
    except Exception:
        terms = []
    if not terms:
        terms = []
    if not speakers:
        speakers = []
    stop_list = ["facebook", "fb", "instagram", "youtube", "tiktok"]
    terms = list(
        filter(lambda x: x.strip() != "" and x.lower() not in stop_list and len(x) < 24, terms)
    )
    terms = terms[:10]
    words = terms + speakers
    logger.debug(f"terms: {terms}")
    logger.debug(f"speakers: {speakers}")
    logger.debug(f"words: {words}")
    if len(words) < 3:
        return None
    else:
        return ", ".join(words) + "."


def join_transcription_and_diarization(transcript_filename, diarization_filename):
    with open(get_abs_path(transcript_filename)) as f:
        transcript = json.load(f)
    try:
        with open(get_abs_path(diarization_filename)) as f:
            diarization = json.load(f)
        # "diarization_segments": [{"start": 0.6, "end": 2.9, "speaker": 0},
        diarization_segments = diarization["diarization_segments"]
    except Exception:
        diarization_segments = [{"start": 0.0, "end": 9999, "speaker": 0}]

    sentence_segments = []
    for segment in transcript["segments"]:
        start = segment["start"]
        end = segment["end"]
        text = segment["text"]
        speaker_id = None
        max_overlap = 0
        for diarization_segment in diarization_segments:
            d_start = diarization_segment["start"]
            d_end = diarization_segment["end"]
            if not (d_start > end or d_end < start):
                overlap_start = max(start, d_start)
                overlap_end = min(end, d_end)
                overlap_duration = overlap_end - overlap_start
                if overlap_duration > max_overlap:
                    max_overlap = overlap_duration
                    speaker_id = diarization_segment["speaker"]
        speaker_tag = "SPEAKER_" + str(speaker_id).zfill(2)
        sentence_segments.append(
            {"sentence": text, "start": start, "end": end, "speaker_id": speaker_tag}
        )
    return sentence_segments


def match_speakers(sentences, title, description, author, window_size=20, model_name=None):
    logger.debug("match_speakers")
    if len(sentences) == 0:
        return sentences
    sentences = sentences.copy()
    speakers = []
    for sentence in sentences:
        if "speaker_id" in sentence:
            if sentence["speaker_id"] not in speakers and sentence["speaker_id"] is not None:
                speakers.append(sentence["speaker_id"])
    speaker_dict = {}  # id -> {name, sentences, first_sentence_index}
    for i, speaker_id in enumerate(speakers):
        sentences_with_speaker = [
            sentence for sentence in sentences if sentence["speaker_id"] == speaker_id
        ]
        first_sentence_index = list(
            map(lambda x: x["speaker_id"] if "speaker_id" in sentence else "", sentences)
        ).index(speaker_id)
        speaker_dict[speaker_id] = {
            "name": speaker_id,
            "speaker_id": speaker_id,
            "sentences": sentences_with_speaker,
            "first_sentence_index": first_sentence_index,
        }
    for speaker_id, speaker_info in speaker_dict.items():
        start_index = max(speaker_info["first_sentence_index"] - window_size, 0)
        end_index = min(start_index + window_size, len(sentences))
        intro_sentences = sentences[start_index:end_index]
        text = ""
        for sentence in intro_sentences:
            if "speaker_id" in sentence and sentence["speaker_id"] is not None:
                text += sentence["speaker_id"] + ": " + sentence["sentence"] + "\n"
        result_plain_text = ollama_wrapper.get_speakers_names(
            text, title, author, description, model_name
        )  # each line is speaker_id: name
        logger.debug("speaker_id: %s", speaker_id)
        logger.debug("result_plain_text: %s", result_plain_text)
        result_plain_text = result_plain_text.split("\n")
        result_plain_text = list(filter(lambda x: len(x.strip()) > 0, result_plain_text))
        result_plain_text = list(
            filter(lambda x: x.strip().startswith("SPEAKER_"), result_plain_text)
        )
        result_plain_text = list(map(lambda x: x.split(": "), result_plain_text))
        result_plain_text = list(
            filter(lambda x: len(x) == 2 and len(x[1]) < 32, result_plain_text)
        )
        result_plain_text = list(
            map(lambda x: {"speaker_id": x[0], "name": x[1]}, result_plain_text)
        )
        result_plain_text = list(filter(lambda x: x["speaker_id"] == speaker_id, result_plain_text))
        result_plain_text = sorted(result_plain_text, key=lambda x: x["name"])
        if len(result_plain_text) > 0:
            speaker_info["name"] = result_plain_text[0]["name"]
        else:
            speaker_info["name"] = speaker_id

    for sentence in sentences:
        if (
            "speaker_id" in sentence
            and sentence["speaker_id"] in speaker_dict
            and sentence["speaker_id"] is not None
        ):
            sentence["speaker_id"] = speaker_dict[sentence["speaker_id"]]["name"]
        else:
            sentence["speaker_id"] = "SPEAKER_" + str(len(speakers))

    detected_speakers = {}
    for index, sentence in enumerate(sentences):
        other_speakers = speaker_dict.values()
        other_speakers = sorted(other_speakers, key=lambda x: -len(x["sentences"]))
        other_speakers = other_speakers[:2]
        if (
            "speaker_id" in sentence
            and sentence["speaker_id"].startswith("SPEAKER_")
            and 0 < index < len(sentences) - 1
        ):
            prev_sentence = sentences[index - 1]
            next_sentence = sentences[index + 1]
            if (
                prev_sentence["speaker_id"] == next_sentence["speaker_id"]
                and prev_sentence["speaker_id"] is not None
                and next_sentence["speaker_id"] != sentence["speaker_id"]
            ):
                for speaker in other_speakers:
                    if speaker["name"] != prev_sentence["speaker_id"]:
                        detected_speakers[sentence["speaker_id"]] = speaker["name"]
                        sentence["speaker_id"] = speaker["name"]
                        break
    for sentence in sentences:
        if "speaker_id" in sentence and sentence["speaker_id"] in detected_speakers:
            sentence["speaker_id"] = detected_speakers[sentence["speaker_id"]]
    return sentences


def generate_final_chapters(
    chapters, sentence_segments, images_with_seconds, language, duration_in_seconds, title
):
    if chapters:
        return chapters
    sentences = sentence_segments  # {"sentence": "телегу", "start": 1549.059, "end": 1549.419}
    seconds_list = [0] + [pair[0] for pair in images_with_seconds] + [duration_in_seconds]
    if len(seconds_list) <= 4:
        chapter_count = 10
        if duration_in_seconds < 2:
            for sentence in sentences:
                if sentence["start"] > duration_in_seconds:
                    duration_in_seconds = sentence["start"]
        if duration_in_seconds < 1800:
            chapter_count = 5
        seconds_list = (
            [0]
            + [(i * duration_in_seconds) // chapter_count for i in range(1, chapter_count)]
            + [duration_in_seconds]
        )
    seconds_pairs = list(zip(seconds_list[:-1], seconds_list[1:], strict=False))
    final_chapters = []
    sentence_index = 0
    for i, (start, end) in enumerate(seconds_pairs):
        if sentence_index >= len(sentences):
            break
        chapter_sentences = [sentence for sentence in sentences if start <= sentence["start"] < end]
        if len(chapter_sentences) == 0:
            continue
        chapter_text = " ".join([sentence["sentence"] for sentence in chapter_sentences])
        chapter_title = generate_title(chapter_text, title, language)
        final_chapters.append(Chapter(chapter_title, start, end - start))
    return final_chapters


def create_initial_model(title, final_chapters, sentence_segments, images_with_seconds, images_dir):
    segments = sentence_segments
    model = []
    if title:
        model.append(("h1", title))
    chapter_index = 0
    sentence_index = 0
    image_index = 0
    while (
        sentence_index < len(segments)
        or image_index < len(images_with_seconds)
        or chapter_index < len(final_chapters)
    ):
        chapter_time = (
            final_chapters[chapter_index].start_seconds
            if chapter_index < len(final_chapters)
            else None
        )
        sentence_time = (
            segments[sentence_index]["start"] if sentence_index < len(segments) else None
        )
        image_time = (
            images_with_seconds[image_index][0] if image_index < len(images_with_seconds) else None
        )
        if (
            chapter_time is not None
            and (sentence_time is None or chapter_time <= sentence_time)
            and (image_time is None or chapter_time <= image_time)
        ):
            model.append(("h2", final_chapters[chapter_index].title))
            chapter_index += 1
        elif (
            sentence_time is not None
            and (image_time is None or sentence_time <= image_time)
            and (chapter_time is None or sentence_time <= chapter_time)
        ):
            speaker_id = segments[sentence_index].get(
                "speaker_id", "SPEAKER_" + str(sentence_index % 10)
            )
            model.append(("p", segments[sentence_index]["sentence"], speaker_id))
            sentence_index += 1
        elif (
            image_time is not None
            and (chapter_time is None or image_time <= chapter_time)
            and (sentence_time is None or image_time <= sentence_time)
        ):
            model.append(("img", images_dir + "/" + images_with_seconds[image_index][1]))
            image_index += 1
    return model


def process_model(model, language):
    newer_model = []
    for item in model:
        if item[0] == "p":
            old_text = item[1]
            speaker_id = item[2] if len(item) > 2 else None
            text = fix_grammar_with_llm(old_text, language)
            newer_model.append(("p", text, speaker_id))
        else:
            newer_model.append(item)
    return newer_model

def translate_model(model, language):
    newer_model = []
    previous_blocks = []
    for item in tqdm(model, desc="Translating model"):
        if item[0] in ["p", "h1", "h2"]:
            old_text = item[1]
            speaker_id = item[2] if len(item) > 2 else None
            context = '\n\n'.join(previous_blocks) if item[0] == "p" and len(previous_blocks) else None
            text = ollama_wrapper.translate(old_text, language, language_to=get_config().translate_to, context=context)
            if item[0] == "p":
                previous_blocks = previous_blocks + [old_text]
                if len(previous_blocks) > 2:
                    previous_blocks = previous_blocks[1:]
            newer_model.append((item[0], text, speaker_id))
        else:
            newer_model.append(item)
    return newer_model


def join_paragraphs(model):
    new_model = []
    for item in model:
        if item[0] in ["h1", "h2", "img"]:
            new_model.append(item)
        elif item[0] == "p":
            if len(new_model) > 0 and new_model[-1][0] == "p":
                # Check if both items have the same speaker ID
                prev_speaker_id = new_model[-1][2] if len(new_model[-1]) > 2 else None
                curr_speaker_id = item[2] if len(item) > 2 else None

                if (
                    prev_speaker_id == curr_speaker_id
                    and len((new_model[-1][1] + " " + item[1]).split(" ")) < 300
                ):
                    new_model[-1] = ("p", new_model[-1][1] + " " + item[1], prev_speaker_id)
                else:
                    new_model.append(item)
            else:
                new_model.append(item)
    return new_model


def select_cover(images_dir, images, video_url):
    if len(images) == 0:
        return None
    return images_dir + "/" + random.choice(images)


def create_output_filename(title):
    ext = get_config().output_format
    return text_helper.clean_title(title) + "." + ext


def model_to_html(model, title):
    inner_html = ""
    prev_p_item = None
    for item in model:
        if item[0] == "h1":
            inner_html += f"<h1>{item[1]}</h1>"
        elif item[0] == "h2":
            inner_html += f"<h2>{item[1]}</h2>"
        elif item[0] == "p":
            if len(item) > 2:
                if (
                    prev_p_item is not None
                    and prev_p_item[0] == "p"
                    and prev_p_item[2] == item[2]
                    or not get_config().diarize
                ):
                    inner_html += f"<p>{item[1]}</p>"
                else:
                    inner_html += f"<p><b>{item[2]}</b> {item[1]}</p>"
            else:
                inner_html += f"<p>{item[1]}</p>"
            prev_p_item = item
        elif item[0] == "img":
            inner_html += f"<img src='{item[1]}'></img>"
        else:
            raise f"model to html, unknown item type {item[0]} {item[1]}"
    html_file = html_helper.save_to_html(title, inner_html)
    return html_file


def add_seconds_to_images(images, count, duration):  # duration in seconds
    result = []  # (seconds, filename)
    for image in images:
        index = int(image.split(".")[0])  # '047.jpg' -> 47
        seconds = index * duration / count
        result.append((seconds, image))
    return result


def split_video(video_filename):  # audio_filename, screenshots_dir
    original_video_file = video_filename
    temp_dir_name = generate_random_filename("screenshots")
    os.makedirs(get_abs_path(temp_dir_name), exist_ok=True)

    try:
        duration = _probe_duration_seconds(video_filename)
    except Exception as e:
        # Log diagnostics to aid debugging and stop early if we cannot get duration
        logger.debug("FFPROBE duration probe failed: %s", e)
        raise

    is_audio = video_filename.split(".")[-1] in ["aac", "ogg", "mp3", "wav"]

    if is_audio:
        return video_filename, temp_dir_name, duration

    "Probe audio codec via ffmpeg banner (avoid unsupported ffprobe flags)"
    codec = _probe_audio_codec(original_video_file)
    logger.debug(f"Audio codec detected: {codec}")

    "ffmpeg -i input_video.mp4 -vn -acodec copy output_audio.mp3"
    if codec == "vorbis":
        codec = "ogg"
    if not codec:
        # Fallback: transcode to mp3 to ensure extraction works on unknown codecs
        codec = "mp3"
        audio_file = generate_random_filename("output_audion", codec)
        extract_audio = ["ffmpeg", "-i", video_filename, "-vn", "-acodec", "libmp3lame", audio_file]
    else:
        audio_file = generate_random_filename("output_audio", codec)
        extract_audio = ["ffmpeg", "-i", video_filename, "-vn", "-acodec", "copy", audio_file]
    result = _run_in_ffmpeg_container(extract_audio, check=False, text=True, capture_output=True)
    logger.debug(
        f"extract audio command: {extract_audio}\nreturn code: {result.returncode}\nstderr: {result.stderr}\nstdout: {result.stdout}"
    )

    "ffmpeg -i input.mp4 -vf fps=1 -vframes 10 screenshot_%04d.jpg"
    img_filename_template = f"{temp_dir_name}/%04d.jpg"
    extract_screenshots = [
        "ffmpeg",
        "-i",
        video_filename,
        "-vf",
        r'"select=not(mod(n\,100))"',
        "-vsync",
        "vfr",
        img_filename_template,
    ]
    result = _run_in_ffmpeg_container(extract_screenshots, text=True, capture_output=True)

    return audio_file, temp_dir_name, duration


def simplify_sentences(sentences):
    result_sentences = []
    trash_dict = [
        "тем не менее",
        ", конечно же,",
        ", может быть,",
        "немножко",
        "разумеется",
        ", вы понимаете,",
        ", но кажется,",
        ", понятно,",
        "ну, правда,",
        "и казалось бы,",
        "по большому счету",
        ", по-моему,",
        "опять же",
        "видимо",
        "боюсь соврать",
        "по крайней мере",
        ", то есть,",
        ", извините,",
        ", на самом деле,",
        "так или иначе",
        "вот эта вот",
        "вот это вот",
        "скажем так",
        "как сказать",
        "так сказать",
        "наверное",
        "немножечко",
        "очевидно",
        ", разумеется,",
        "скорее всего",
        "естественно",
        "сколько там",
        ", ну,",
        "ну и так далее",
        "вот этих вот",
        "так вот",
        "вот",
        "как бы",
        "кстати",
        "честно говоря",
        "что называется",
        "к сожалению",
        "не дай бог",
        "дай бог",
        " в общем-то",
        "в общем",
        "...",
    ]
    long_trash_dict = []
    for t in trash_dict:
        long_trash_dict.append(t)
        long_trash_dict.append(t.capitalize())
        long_trash_dict.append(t.upper())
    long_trash_dict = [
        t(ltd)
        for ltd in long_trash_dict
        for t in [
            lambda x: f", {x},",
            lambda x: x + "...",
            lambda x: x + ".",
            lambda x: x + ",",
            lambda x: x,
        ]
    ]
    for sentence in sentences:
        text: str = sentence["sentence"]
        for trash in long_trash_dict:
            if text.replace(trash, "").strip() != text.strip():
                if trash == "...":
                    parts = text.split("... ")
                    parts_lower = [parts[0]]
                    for part in parts[1:]:
                        parts_lower.append(part[0].lower() + part[1:])
                    options = {"a": ", ".join(parts_lower), "b": " ".join(parts_lower)}
                    ollama_wrapper.choose_best_option(None, None, options)
                    text2 = options.get("c", options["a"])
                else:
                    text2 = text.replace(trash, "")
                text2 = text2.replace("  ", " ")
                if text2.startswith(" "):
                    text2 = text2[1:]
                    text2 = text2.capitalize()
                if text2.endswith(" "):
                    text2 = text2[:-1]
                    text2 = text2 + text[-1]
                text2 = text2.replace(", .", ".")
                text2 = text2.replace(",.", ".")
                text2 = text2.replace(" ,", ",")
                text2 = text2.replace(",,", ",")
                text2 = text2.replace(". .", ".")
                text2 = text2.replace(" .", ".")
                logger.debug(f"deleted trash: `{trash}`\ncontext: `{text}`\nresult `{text2}`")
                text = text2
        speaker_id = sentence.get("speaker_id", "SPEAKER_NONE")
        if text.strip() != "":
            result_sentences.append(
                {
                    "sentence": text,
                    "speaker_id": speaker_id,
                    "start": sentence["start"],
                    "end": sentence["end"],
                }
            )
    return result_sentences
