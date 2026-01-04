import logging
import sys


class _MaxLevelFilter(logging.Filter):
    def __init__(self, max_level: int) -> None:
        super().__init__()
        self.max_level = max_level

    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        return record.levelno <= self.max_level


def setup_logging(verbose: bool = False) -> None:
    """
    Configure root logging.

    - By default (verbose == False): output INFO messages to stdout, and WARNING+ to stderr.
    - With verbose: also include DEBUG messages to stdout.
    - Timestamps/format kept compact for CLI use.
    """
    # Clear existing handlers to make the setup idempotent.
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)

    root.setLevel(logging.DEBUG if verbose else logging.INFO)

    # Formatter
    fmt = "%(levelname)s: %(name)s: %(message)s"
    formatter = logging.Formatter(fmt)

    # Stdout handler: DEBUG/INFO when verbose, otherwise INFO only
    stdout_handler = logging.StreamHandler(stream=sys.stdout)
    stdout_handler.setFormatter(formatter)
    if verbose:
        stdout_handler.addFilter(_MaxLevelFilter(logging.INFO))  # DEBUG and INFO to stdout
        stdout_handler.setLevel(logging.DEBUG)
    else:
        stdout_handler.addFilter(_MaxLevelFilter(logging.INFO))  # only up to INFO
        stdout_handler.setLevel(logging.INFO)

    # Stderr handler: WARNING and above
    stderr_handler = logging.StreamHandler(stream=sys.stderr)
    stderr_handler.setFormatter(formatter)
    stderr_handler.setLevel(logging.WARNING)

    root.addHandler(stdout_handler)
    root.addHandler(stderr_handler)
