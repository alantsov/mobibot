from src.loaders import yt_dlp_loader
from src.pipeline import one_of


def load_media(link_to_video_or_podcast):
    loaders = [
        yt_dlp_loader.yt_dlp_with_auto_dubbing,
        yt_dlp_loader.yt_dlp_no_recode,
        yt_dlp_loader.yt_dlp_recode,
    ]
    return one_of(loaders, link_to_video_or_podcast)
