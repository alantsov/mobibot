import json
import logging
import re

import ollama
from pydantic import BaseModel
from tqdm import tqdm

logger = logging.getLogger(__name__)


logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

OLLAMA_PORT = 11434

REQUIRED_MODELS = {
    "hy-mt1.5-7b:q8": {
        "from": "hf.co/tencent/HY-MT1.5-7B-GGUF:Q8_0",
        "template": '{{ if .System }}<|startoftext|>{{ .System }}<|extra_4|>{{ end }}{{ if .Prompt }}<|startoftext|>{{ .Prompt }}<|extra_0|>{{ end }}{{ .Response }}<|eos|>',
        "options": {
            "top_k": 20,
            "top_p": 0.6,
            "repetition_penalty": 1.05,
            "temperature": 0.7,
        },
    },
    "hy-mt1.5-7b:q4": {
        "from": "hf.co/tencent/HY-MT1.5-7B-GGUF:Q4_K_M",
        "template": '{{ if .System }}<|startoftext|>{{ .System }}<|extra_4|>{{ end }}{{ if .Prompt }}<|startoftext|>{{ .Prompt }}<|extra_0|>{{ end }}{{ .Response }}<|eos|>',
        "options": {
            "top_k": 20,
            "top_p": 0.6,
            "repetition_penalty": 1.05,
            "temperature": 0.7,
        },
    },
}


def set_ollama_port(port):
    global OLLAMA_PORT
    OLLAMA_PORT = port


def get_ollama_base():
    return f"http://localhost:{OLLAMA_PORT}"


def _create_model(client, model_name, from_model, template):
    logger.info("Creating model %s from %s", model_name, from_model)
    client.create(model=model_name, from_=from_model, template=template)


def _load_model(client, model_name):
    current_digest, bars = "", {}
    ollama_progress = client.pull(model_name, stream=True)
    for progress in ollama_progress:
        digest = progress.get("digest", "")
        if digest != current_digest and current_digest in bars:
            bars[current_digest].close()

        if not digest:
            logger.debug("ollama pull status: %s", progress.get("status"))
            continue

        if digest not in bars and (total := progress.get("total")):
            bars[digest] = tqdm(
                ollama_progress,
                total=total,
                desc=f"pulling {digest[7:19]}",
                unit="B",
                unit_scale=True,
            )

        if completed := progress.get("completed"):
            bars[digest].update(completed - bars[digest].n)

        current_digest = digest


def _call_ollama_chat(
    prompt,
    model=None,
    temperature=0.1,
    max_tokens=4096,
    num_predict=4096,
    keep_alive=10,
    images=None,
    think=None,
    format=None,
):
    """
    Helper method to handle common functionality for ollama.chat calls.

    Args:
        prompt (str): The prompt to send to the model
        model (str, optional): The model to use. Defaults to 'gemma3:12b' if None.
        temperature (float, optional): Temperature parameter. Defaults to 0.1.
        max_tokens (int, optional): Maximum tokens to generate. Defaults to 4096.
        num_predict (int, optional): Number of tokens to predict. Defaults to 4096.
        keep_alive (int, optional): Keep alive parameter. Defaults to 10.
        images (list, optional): List of image paths to include. Defaults to None.

    Returns:
        str: The content of the model's response
    """

    if model is None:
        model_name = "ministral-3:8b"
    else:
        model_name = model

    message = {"role": "user", "content": prompt}
    if images:
        message["images"] = images

    options = {"temperature": temperature, "max_tokens": max_tokens, "num_predict": num_predict}
    if model_name in REQUIRED_MODELS:
        options.update(REQUIRED_MODELS[model_name].get("options", {}))

    client = ollama.Client(host=get_ollama_base())
    if model_name not in list(map(lambda x: x.model, client.list().models)):
        if model_name in REQUIRED_MODELS:
            _create_model(
                client,
                model_name,
                REQUIRED_MODELS[model_name]["from"],
                REQUIRED_MODELS[model_name]["template"],
            )
        else:
            logger.debug("model %s not found, downloading...", model_name)
            _load_model(client, model_name)

    json_res = client.chat(
        model=model_name,
        messages=[message],
        options=options,
        think=think,
        keep_alive=keep_alive,
        format=format,
    )

    return json_res["message"]["content"]


def extract_chapters(description):
    class ChapterInfo(BaseModel):
        chapter_time_hours: int
        chapter_time_minutes: int
        chapter_time_seconds: int
        chapter_title: str

    class ChaptersInfo(BaseModel):
        chapters: list[ChapterInfo]

    prompt = f"""
    you will be provided podcast description.
    it could contain chapters.
    if not just return single word `None`.
    if it contains chapters return each one on a new line.
    format should be: `hh:mm:ss title`.
    description: ```{description}```
    """
    logger.debug("Prompt (extract_chapters): %s", prompt)
    chapters_text = _call_ollama_chat(
        prompt, model="ministral-3:8b", format=ChaptersInfo.model_json_schema()
    )
    logger.debug("Result (extract_chapters): %s", chapters_text)
    chapters_info = ChaptersInfo.model_validate_json(chapters_text)
    chapters = []
    for chapter in chapters_info.chapters:
        chapters.append(
            f"{chapter.chapter_time_hours}:{chapter.chapter_time_minutes}:{chapter.chapter_time_seconds} {chapter.chapter_title}"
        )
    return chapters


def extract_text_from_screenshot(image_path):
    prompt = "extract text from screenshot. do not comment text itself, provide only text, do not use markdown, use only text."
    result = _call_ollama_chat(
        prompt,
        model="ministral-3:8b",
        temperature=0.35,
        max_tokens=256,
        num_predict=256,
        images=["data/" + image_path],
    )
    return result.strip("\n").replace("`", "").replace('"', "")


def extract_title_and_author_from_image(image_path):
    class BookInfo(BaseModel):
        title: str
        author: str

    prompt = (
        "extract book title and author, in case of multiple authors, provide only the first one."
    )
    book_info_json = _call_ollama_chat(
        prompt,
        images=["data/" + image_path],
        model="ministral-3:8b",
        temperature=0,
        format=BookInfo.model_json_schema(),
    )
    book_info = BookInfo.model_validate_json(book_info_json)
    return book_info.title, book_info.author


def extract_terms(text, description, title):
    class TermsInfo(BaseModel):
        terms: list[str]

    prompt = f"""Extract technical terms from text below, do not comment text itself, provide only terms, do not use punctuation.
text: ```{text}```
title: ```{title}```
description: ```{description}```
provide answer in json format"""
    logger.debug("%s %s", len(prompt), prompt)
    result = _call_ollama_chat(
        prompt, model="ministral-3:8b", temperature=0, format=TermsInfo.model_json_schema()
    )
    terms_info = TermsInfo.model_validate_json(result)
    return terms_info.terms


def filter_terms(list_of_terms):
    class TermsInfo(BaseModel):
        terms: list[str]

    list_of_terms = list(set(list_of_terms))
    text = "\n".join(list_of_terms)
    prompt = f"""You are given a list of technical terms and common words. 
    filter out common words, copy to answer only technical terms, do not comment, provide only terms, do not use punctuation.
list of terms:\n```{text}```
provide answer in json format.
"""
    result = _call_ollama_chat(
        prompt, model="ministral-3:8b", temperature=0, format=TermsInfo.model_json_schema()
    )
    terms_info = TermsInfo.model_validate_json(result)
    return terms_info.terms


def generate_title(text, title, lang="ru"):
    class TitleInfo(BaseModel):
        title: str

    language = {"ru": "russian", "en": "english"}[lang]
    text = text.replace("\n\n", "\n")
    prompt = f"""generate one line title for text below, do not comment text itself, provide only title, do not use punctuation.
do not use markdown, use only text.
Use {language} language. Title should be short, simple and descriptive
context: this is chapter of transcription of audio 
you will be provided with title for whole text and chapter text:
title for whole text: ```{title}``` 
chapter text: ```{text}```
and again use {language} language and provide only title, title should as short as possible and as simple as possible
provide answer in json format"""
    prompt = prompt.strip()
    logger.debug("%s %s", len(prompt), prompt)
    result = _call_ollama_chat(
        prompt, model="ministral-3:8b", temperature=0.0, format=TitleInfo.model_json_schema()
    )
    logger.debug("%s %s %s", "result:\n", result, "\n")
    title_info = TitleInfo.model_validate_json(result)
    title = title_info.title
    title = (
        title.split("\n")[0]
        .replace("`", "")
        .replace('"', "")
        .replace("Title:", "")
        .replace("*", "")
        .strip()
    )
    cleaned_title = re.sub(r"[^а-яА-ЯA-Za-z0-9 ]+", "", title)
    return cleaned_title


def extract_speakers_names(text, title, description, channel_title):
    prompt = f"""
    You are an NER extractor. Output only JSON. No extra text.
    Extract all person names from this text:
    title: ```{title}```
    description: ```{description}```
    channel title: ```{channel_title}```
    text: ```{text}```
    """

    format_dict = {
        "type": "object",
        "properties": {"names": {"type": "array", "items": {"type": "string"}}},
        "required": ["names"],
    }

    result = _call_ollama_chat(prompt, model="ministral-3:8b", format=format_dict)
    result_dict = json.loads(result)
    speakers = result_dict["names"]
    logger.debug(f"extract_speakers_names speakers: {speakers}")
    return speakers


def extract_downloadable_links(html_content, links_block):
    prompt = f"""
    You are an http link extractor. Output only JSON. No extra text.
    extract link to audio file for podcast episode
    you will be given html content of podcast episode and list of links in triple backquotes
    html content: 
    ```{html_content}```
    links: 
    ```{links_block}```
    your answer should provide link itself and nothing else
    first line should be link to audio file
    """
    format_dict = {
        "type": "object",
        "properties": {"links": {"type": "array", "items": {"type": "string"}}},
        "required": ["links"],
    }
    result = _call_ollama_chat(prompt, model="ministral-3:8b", temperature=0, format=format_dict)
    result_dict = json.loads(result)
    links = result_dict["links"]
    return links


def extract_description(html_content):
    class PodcastEpisodeInfo(BaseModel):
        description: str

    prompt = f"""
    extract description of podcast episode
    you will be given html content of podcast episode page
    provide episode description
    do not provide anything else, only description
    do not use markdown, use only text.
    do not comment anything.
    html content: ```{html_content}```
    provide answer in json format
    """
    logger.debug(f"Prompt (extract_description): {prompt}")
    result = _call_ollama_chat(
        prompt,
        model="ministral-3:8b",
        temperature=0.0,
        format=PodcastEpisodeInfo.model_json_schema(),
    )
    logger.debug(f"Result (extract_description): {result}")
    podcast_info = PodcastEpisodeInfo.model_validate_json(result)
    return podcast_info.description


def extract_episode_title_and_podcast_name(html_content):
    class EpisodeInfo(BaseModel):
        title: str
        podcast_name: str

    prompt = f"""
    extract episode title and podcast name from html page about podcast episode
    you will be given html content of podcast episode page in triple backquotes
    do not use markdown, use only text.
    do not provide anything else, only title and podcast name
    html content: ```{html_content}```
    """
    result = _call_ollama_chat(
        prompt, model="ministral-3:8b", temperature=0.0, format=EpisodeInfo.model_json_schema()
    )
    episode_info = EpisodeInfo.model_validate_json(result)
    return episode_info.title, episode_info.podcast_name


def extract_rss_links(html_content):
    class PodcastInfo(BaseModel):
        rss_link: str

    prompt = f"""
        extract link to rss feed for podcast

        provide link as is, do not change it
        html content: 
        ```{html_content}```
        """
    result = _call_ollama_chat(
        prompt, model="ministral-3:8b", temperature=0, format=PodcastInfo.model_json_schema()
    )
    podcast_info = PodcastInfo.model_validate_json(result)
    return podcast_info.rss_link


def extract_podcast_name(episode_podcast_name):
    class PodcastName(BaseModel):
        podcast_name: str

    prompt = f"""
            you will be given podcast name with some marketing nonsense at the end in triple backquotes: 
            ```{episode_podcast_name}```
            provide podcast name only in json format
            """
    result = _call_ollama_chat(
        prompt, model="ministral-3:8b", temperature=0, format=PodcastName.model_json_schema()
    )
    podcast_name = PodcastName.model_validate_json(result)["podcast_name"]
    return podcast_name


def get_speakers_names(text, title, author, description, model=None):
    class SpeakerInfo(BaseModel):
        speaker_id: str
        speaker_name: str

    class SpeakersInfo(BaseModel):
        speakers: list[SpeakerInfo]

    prompt = f"""
detect name for each speaker in text.
you will be given video title, channel/author, description and text with speaker id, like SPEAKER_02. 
your task is to provide name for each speaker id.
title: ```{title}```
channel/author: ```{author}```
description: ```{description}```
text: ```{text}```
include in answer only speakers with identified names
provide answer in json format"""
    prompt = prompt.strip("")
    if not model:
        model = "ministral-3:8b"
    logger.debug("prompt: %s", prompt)
    result = _call_ollama_chat(
        prompt, model=model, temperature=0.0, think=False, format=SpeakersInfo.model_json_schema()
    )
    logger.debug("result: %s", result)
    speakers_info = SpeakersInfo.model_validate_json(result)
    names_text = ""
    for speaker in speakers_info.speakers:
        names_text += speaker.speaker_id + ": " + speaker.speaker_name + "\n"
    logger.debug("names_text: %s", names_text)
    return names_text


def choose_best_option(text, error_message, options: dict[str, str]):
    """
    Ask LLM to choose the best option and return a valid option key.

    Uses structured JSON output to ensure the result is one of the provided keys.
    Falls back to lightweight sanitization if the model returns malformed data.
    """
    # Build a readable options block for the prompt
    options_block = "\n".join([f"{k}: {v}" for k, v in options.items()])

    # JSON schema to force the model to select only from provided keys
    allowed_keys = list(options.keys())
    json_schema = {
        "type": "object",
        "properties": {"option": {"type": "string", "enum": allowed_keys}},
        "required": ["option"],
        "additionalProperties": False,
    }

    base_prompt = """
Act as a professional corrector.
You will be given a list of options{ctx_note}. Your task is to choose the best option.

Options:
```
{options_block}
```
{extra}

Return your answer strictly as JSON that matches the provided schema.
""".strip()

    ctx_note = " with an error message and context" if text and error_message else ""
    extra_parts = []
    if error_message:
        extra_parts.append(f"Error message:\n```\n{error_message}\n```")
    if text:
        extra_parts.append(f"Context:\n```\n{text}\n```")
    extra = "\n".join(extra_parts)

    prompt = base_prompt.format(ctx_note=ctx_note, options_block=options_block, extra=extra)

    logger.debug("prompt: %s", prompt)
    model = "ministral-3:8b"
    result = _call_ollama_chat(prompt, model=model, temperature=0.0, format=json_schema)
    chosen_key = None
    try:
        data = json.loads(result)
        key = data.get("option")
        if isinstance(key, str) and key in options:
            chosen_key = key
    except Exception:
        pass

    logger.debug("option: %s", chosen_key)
    return chosen_key


def translate(text, language="ru", language_to="english"):
    model = "hy-mt1.5-7b:q4"
    if language == "zh":
        prompt = f"""把下面的文本翻译成英语，不要额外解释。

{text}"""
    else:
        prompt = f"""
Translate the following segment into {language_to}, without additional explanation.

{text}
"""
    result = _call_ollama_chat(prompt, model=model)
    logger.debug("text: %s", text)
    logger.debug("result: %s", result)
    return result


def ocr_with_deepseek_grounding(image_path):
    prompt = "<image>\n<|grounding|>Convert the document to markdown."
    result = _call_ollama_chat(
        prompt, model="deepseek-ocr:latest", temperature=0.0, images=[image_path]
    )
    return result


def ocr_with_deepseek(image_path):
    prompt = "<image>\nConvert the document to markdown."
    result = _call_ollama_chat(
        prompt, model="deepseek-ocr:latest", temperature=0.0, images=[image_path]
    )
    return result
