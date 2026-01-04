from src.wrappers import docker_wrapper


def _run_in_ffmpeg_container(cmd_args, check=False, text=True, capture_output=True):
    command = [" ".join(cmd_args)]
    return docker_wrapper.run_docker_container("ffmpeg", command, capture_output=True)


def _probe_duration_seconds(path: str) -> int:
    """
    Robustly probe media duration in seconds using Dockerized tools.
    Prefer parsing the Duration banner from ffmpeg (widely compatible),
    with ffprobe banner as a secondary fallback. Returns floor(seconds) as int.
    Raises ValueError if duration cannot be determined.
    """
    # 1) Try ffmpeg banner (most compatible across images)
    ffmpeg_banner_cmd = ["ffmpeg", "-i", path]
    res = _run_in_ffmpeg_container(ffmpeg_banner_cmd, text=True, capture_output=True)
    err = res.stderr or ""
    # Parse Duration: HH:MM:SS.xx
    import re

    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+)(?:[\.,](\d+))?", err)
    if m:
        h, mnt, s, frac = m.groups()
        total = int(h) * 3600 + int(mnt) * 60 + int(s)
        return int(total)

    # 2) Fallback: ffprobe banner without flags (some builds lack show_entries/select_streams)
    banner_cmd = ["ffprobe", path]
    res = _run_in_ffmpeg_container(banner_cmd, text=True, capture_output=True)
    err = res.stderr or ""
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+)(?:[\.,](\d+))?", err)
    if m:
        h, mnt, s, frac = m.groups()
        total = int(h) * 3600 + int(mnt) * 60 + int(s)
        return int(total)

    raise ValueError("Unable to determine duration via ffmpeg/ffprobe banners")


def _probe_audio_codec(path: str):
    """
    Determine audio codec by parsing ffmpeg/ffprobe banners inside Docker.
    Returns codec name in lowercase, or None if not found.
    """
    res = _run_in_ffmpeg_container(["ffmpeg", "-i", path], text=True, capture_output=True)
    err = res.stderr or ""
    import re

    m = re.search(r"Audio:\s*([A-Za-z0-9_]+)", err)
    if m:
        return m.group(1).lower()
    # Fallback to ffprobe banner parsing
    res = _run_in_ffmpeg_container(["ffprobe", path], text=True, capture_output=True)
    err = res.stderr or ""
    m = re.search(r"Audio:\s*([A-Za-z0-9_]+)", err)
    if m:
        return m.group(1).lower()
    return None
