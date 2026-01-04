from dataclasses import dataclass


@dataclass
class Chapter:
    title: str
    start_seconds: float
    duration: float  # in seconds
