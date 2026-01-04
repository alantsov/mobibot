import os
import uuid
from pathlib import Path


def generate_random_filename(prefix: str, extension: str = None) -> str:
    if not extension:
        return f"{prefix}_{uuid.uuid4()}"
    else:
        return f"{prefix}_{uuid.uuid4()}.{extension}"


def normalize_filepath_to_data(filepath) -> str:
    # Normalize path for ffmpeg container: make it relative to data/ when possible
    data_dir = Path("data").resolve()
    p = Path(filepath)

    # If already like 'data/...', strip the leading 'data/' part
    s = str(filepath)
    data_prefix = "data" + os.sep
    if s.startswith(data_prefix):
        rel = s[len(data_prefix) :]
    else:
        if p.is_absolute():
            try:
                rel = str(p.resolve().relative_to(data_dir))
            except Exception:
                # Fallback: use basename; this will work only if the file is in data root
                rel = p.name
        else:
            # If it's a relative path but not prefixed with data/, assume it's already relative to data/
            rel = s
    return rel


def get_abs_path(rel_path: str) -> str:
    """Converts a relative path (from data dir) to an absolute path."""
    if not rel_path:
        return rel_path
    if os.path.isabs(rel_path):
        return rel_path
    if rel_path.startswith("data" + os.sep):
        return os.path.abspath(rel_path)
    return os.path.abspath(os.path.join("data", rel_path))


def get_rel_path(path: str) -> str:
    """Converts a path to a relative path from the data dir."""
    return normalize_filepath_to_data(path)
