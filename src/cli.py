#!/usr/bin/env python3
import argparse
import logging
import os
import shutil
import sys

import src.config as config
import src.router as router
from src.logging_setup import setup_logging


def parse_args():
    argv = sys.argv[1:]
    if len(argv) > 0 and argv[0] == "--":
        argv = argv[1:]
    parser = argparse.ArgumentParser(
        description="MobiBot CLI: process a link or a file into an e-reader-friendly format."
    )
    parser.add_argument(
        "input",
        help="A URL, a path to a local file (audio/image/pdf/ebook/html), or a plain text query.",
    )
    parser.add_argument(
        "--start-from",
        help="stage of pipeline, you would like to start from (default: first stage)",
    )
    parser.add_argument(
        "--translate-to", help="Translate to English (en) or Russian (ru), default: no translation"
    )
    parser.add_argument("--output-format", help="epub | mobi | txt")
    parser.add_argument(
        "--diarize", action="store_true", help="Enable diarization (default: disabled)"
    )
    parser.add_argument(
        "--simplify-transcript", action="store_true", help="Simplify transcript (default: disabled)"
    )
    parser.add_argument('--fix-grammar', action='store_true', help='Fix grammar (default: disabled)')
    parser.add_argument(
        "--config", help="yaml file with configuration overrides", default="config.yaml"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print all logs to stdout/stderr (default: only pipeline and docker utils)",
    )
    return parser.parse_args(argv)


def process_input(value: str) -> tuple[str, str]:
    os.makedirs("data", exist_ok=True)
    value = value.strip()
    if os.path.isfile(value):
        new_path = os.path.join("data", os.path.basename(value))
        shutil.copy2(value, new_path) if not value.startswith("data") else None
        value = new_path
        out = router.convert_to_mobi(value)
        return out, ""
    out, err = router.handle_text_message(value)
    return out, err


def main():
    args = parse_args()
    verbose = args.verbose
    setup_logging(verbose)
    logger = logging.getLogger(__name__)

    cli_config = {
        k: v
        for k, v in vars(args).items()
        if v is not None and k not in ["input", "verbose", "config"]
    }

    config.init_config(config_path=args.config, cli_args=cli_config)
    output, error = process_input(args.input)
    if error:
        logger.error(error, exc_info=True)
    else:
        logger.info(output)


if __name__ == "__main__":
    main()
