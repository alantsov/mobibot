# MobiBot

Convert videos, audio, and articles into e‑reader‑friendly files you can load and read on Kindle, Kobo, or any EPUB/MOBI e-ink reader.

## Supported inputs
- **URLs**: YouTube (videos, playlists, livestreams), archive.org, Bitchute, and other video hosting sites.
- **Article URLs**: Many standard article pages and blog posts (e.g., Arxiv, Substack, Medium).
- **Local files**:
  - Documents: `pdf`, `djvu`, `html`, `htm`
  - Audio: `mp3`, `ogg`, `wav`, `aac`
  - Video: `mp4`, `mkv`, `webm`

## Supported outputs
- **EPUB**: for most e-ink readers
- **MOBI**: for Kindle e-ink readers

## Quick start (using uv)
Prerequisites:
- [uv](https://docs.astral.sh/uv/) installed
- Docker Desktop or Docker Engine running
- NVIDIA GPU with [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html) (highly recommended for OCR and speech-to-text)

No need to configure anything, just run the following:

```bash
git clone https://github.com/alantsov/mobibot.git
cd mobibot
uv run mobibot https://arxiv.org/abs/1706.03762
```

If processing succeeds, the CLI prints the resulting file path and also copies it to the `output/` directory.

more examples:
```bash
# convert a YouTube video into an epub file (will use speach to text and llm's)
uv run mobibot https://www.youtube.com/watch?v=zjkBMFhNj_g

# convert a youtube video into a mobi file
uv run mobibot https://www.youtube.com/watch?v=zjkBMFhNj_g --output-format mobi

# convert a youtube video into an epub file in your language
uv run mobibot https://www.youtube.com/watch?v=zjkBMFhNj_g --translate-to ru

# convert an article into an epub file
uv run mobibot https://arxiv.org/abs/1706.03762

# convert a local pdf/djvu file into an epub file (will use OCR and error correction)
uv run mobibot samples/bitter_lesson.pdf

# convert a local file into an epub file in your langauge
uv run mobibot samples/bitter_lesson.pdf --translate-to ru

# convert a local file into a mobi file
uv run mobibot samples/bitter_lesson.pdf --output-format mobi
```

## CLI usage
```
MobiBot CLI: process a link or a file into an e-reader-friendly format.

positional arguments:
  input                 A URL or a path to a local file (audio/video/pdf/djvu/html)

optional arguments:
  --translate-to LANG      Translate to any language (e.g., en, ru, cs, de); default: no translation
  --output-format FORMAT   Output file format: epub, mobi, or txt; default: epub
  --diarize                Enable speaker diarization for audio/video (default: disabled)
  --simplify-transcript    Simplify and clean up the transcript using LLM (default: disabled)
  --start-from STAGE       Stage of pipeline to start from (e.g., download, transcribe, etc.)
  --config CONFIG_FILE     YAML file with configuration overrides (default: config.yaml)
  --verbose                Print all logs to stdout/stderr (default: only pipeline and docker utils)
```

Output:
- The final file path is printed to stdout on success.
- A copy is placed in `output/`.

## How to use --start-from
```
# convert a YouTube video into an epub file
> uv run mobibot https://www.youtube.com/watch?v=zjkBMFhNj_g
Trying to load https://www.youtube.com/watch?v=zjkBMFhNj_g
Will iterate 4 loaders: ['yt_dlp_with_auto_dubbing', 'yt_dlp_without_auto_dubbing', 'yt_dlp_no_recode', 'yt_dlp_recode']
  Trying yt_dlp_with_auto_dubbing, 1/4
    Failed yt_dlp_with_auto_dubbing, trying next one
  Trying yt_dlp_without_auto_dubbing, 2/4
    Success yt_dlp_without_auto_dubbing
load_media done 1/18 in 23.78s
split_video done 2/18 in 5.44s
guess_language done 3/18 in 0.00s
select_screenshots_by_CLIP_model done 4/18 in 14.48s
add_seconds_to_images done 5/18 in 0.00s
audio_to_json done 6/18 in 526.72s
join_transcription_and_diarization done 7/18 in 0.01s
simplify_sentences done 8/18 in 0.00s
match_speakers done 9/18 in 0.00s
generate_final_chapters done 10/18 in 2.59s
create_initial_model done 11/18 in 0.00s
process_model done 12/18 in 785.57s
select_cover done 13/18 in 0.00s
model_to_html done 14/18 in 0.00s
translate_html_file done 15/18 in 0.00s
create_output_filename done 16/18 in 0.00s
create_cover done 17/18 in 0.05s
convert_book done 18/18 in 0.87s
INFO: __main__: _1hr_Talk__Intro_to_Large_Language_Models.epub

# pick stage to start from (for example translate_html_file)
>  uv run mobibot https://www.youtube.com/watch?v=zjkBMFhNj_g --translate-to ru --start-from translate_html_file
load_media skipped
split_video skipped
guess_language skipped
select_screenshots_by_CLIP_model skipped
add_seconds_to_images skipped
audio_to_json skipped
join_transcription_and_diarization skipped
simplify_sentences skipped
match_speakers skipped
generate_final_chapters skipped
create_initial_model skipped
process_model skipped
select_cover skipped
model_to_html skipped
Translating text in html tags: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 76/76 [03:29<00:00,  2.76s/it]
translate_html_file done 15/18 in 212.93s
create_output_filename done 16/18 in 0.00s
create_cover done 17/18 in 0.04s
convert_book done 18/18 in 0.67s
INFO: src.cli: _1hr_Talk__Intro_to_Large_Language_Models.epub
```

Explanation:
in the first run, all intermediate artifacts are saved
in the second run, those artifacts are reused for 14 stages and saved 10+ minutes


## Where do results go?
- A successful run prints the full path of the generated file and also copies it to `output/`.
- Intermediate working files (like downloaded videos, extracted audio, or raw transcripts) are stored in the `data/` folder.

## Troubleshooting
- "unknown error" or exit code 1: rerun with `--verbose` to see details.

## License
MobiBot is licensed under the GNU Affero General Public License v3.0 (AGPL‑3.0‑only).
- See the `LICENSE` file at the repository root for the full text.
