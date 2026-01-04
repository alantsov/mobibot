import requests

TIKTOKEN_PORT = 8300


def set_tiktoken_port(port: int) -> None:
    global TIKTOKEN_PORT
    TIKTOKEN_PORT = int(port)


def get_tiktoken_base() -> str:
    return f"http://localhost:{TIKTOKEN_PORT}"


def encode(text: str, encoding_name: str = "o200k_base") -> list[int]:
    resp = requests.post(
        f"{get_tiktoken_base()}/encode",
        json={"text": text, "encoding": encoding_name},
        timeout=5.0,
    )
    resp.raise_for_status()
    data = resp.json()
    tokens = data.get("tokens")
    if not isinstance(tokens, list):
        raise ValueError("Invalid response from tiktoken service: missing 'tokens' list")
    return [int(t) for t in tokens]
