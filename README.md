# MobiBot

Convert videos, audio, and articles into e‑reader‑friendly files you can load on Kindle, Kobo, or any EPUB/MOBI reader.

MobiBot can:
- Download and process videos and playlists
- process audio files
- Extract and clean article text (with Readability)
- Perform OCR and speech‑to‑text when needed
- Generate covers and format output for e‑readers
- Produce EPUB/MOBI files and place them in the `output/` folder


## Quick start (using uv)
Prerequisites:
- [uv](https://docs.astral.sh/uv/) installed
- Docker Desktop or Docker Engine running
- NVIDIA GPU with [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html) (highly recommended for OCR and speech-to-text)

```bash
git clone https://github.com/alantsov/mobibot.git
cd mobibot
uv run src/cli.py https://arxiv.org/abs/1706.03762
```

If processing succeeds, the CLI prints the resulting file path and also copies it to the `output/` directory.

## CLI usage
```
MobiBot CLI: process a link or a file into an e-reader-friendly format.

positional arguments:
  input                 A URL, a path to a local file (audio/image/pdf/ebook/html), or a plain text query.

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

## Supported inputs
- **URLs**: YouTube (videos, playlists, livestreams), archive.org, Bitchute, CERN Document Server.
- **Article URLs**: Many standard article pages and blog posts (e.g., Arxiv, Substack, Medium).
- **Local files**:
  - Documents: `pdf`, `djvu`, `html`, `htm`
  - Audio: `mp3`, `ogg`, `wav`, `aac`
  - Video: `mp4`, `mkv`, `webm`
- **Plain text**: MobiBot will try to extract links from text and process the first one it finds.

## Where do results go?
- A successful run prints the full path of the generated file and also copies it to `output/`.
- Intermediate working files (like downloaded videos, extracted audio, or raw transcripts) are stored in the `data/` folder.

## Troubleshooting
- "unknown error" or exit code 1: rerun with `--verbose` to see details.

## License
MobiBot is licensed under the GNU Affero General Public License v3.0 (AGPL‑3.0‑only).
- See the `LICENSE` file at the repository root for the full text.
