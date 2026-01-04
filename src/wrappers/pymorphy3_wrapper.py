import json
import os

from src.wrappers import docker_wrapper

PYMORPHY3_DOCKER_IMAGE = os.environ.get("PYMORPHY3_DOCKER_IMAGE", "pymorphy3_nlp:0.0.1")


def _run_pymorphy3_container(language: str, names: list[str]) -> list[list[str]]:
    """
    Run pymorphy3 inside a Docker image. The container reads JSON from argv/stdin
    and prints a JSON object with a "base_names" field to stdout.

    Input JSON schema:
      {
        "language": "ru" | "en" | ...,
        "names": ["Александру", "Марии", ...]
      }

    Output JSON schema:
      {
        "base_names": [["Александр"], ["Мария"], ...]
      }

    For non-Russian languages, the container is expected to return the names unchanged.
    """
    # Ensure input is a list of strings
    names = [n for n in names if isinstance(n, str)]

    payload = json.dumps(
        {
            "language": language,
            "names": names,
        }
    )

    proc = docker_wrapper.run_docker_container("pymorphy3", [payload], capture_output=True)

    if proc.returncode != 0:
        raise RuntimeError(
            f"pymorphy3 container failed.\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )

    stdout = proc.stdout.strip()

    # Try to find the last JSON object in output (ignore logs)
    json_text = None
    for line in stdout.splitlines()[::-1]:
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            json_text = line
            break
    if json_text is None:
        json_text = stdout

    try:
        data = json.loads(json_text)
    except Exception as e:
        raise RuntimeError(f"Failed to parse JSON from pymorphy3 output: {e}. Raw:\n{stdout}")

    if "error" in data:
        raise RuntimeError(f"pymorphy3 error: {data['error']}")

    base_names = data.get("base_names", [])
    if not isinstance(base_names, list):
        raise RuntimeError(f"Invalid response from pymorphy3: {data}")
    return base_names


def extract_base_names(name: str, lang: str) -> list[str]:
    """Return a list of candidate base forms for a single name.

    Keeps the previous API used by callers.
    """
    if not isinstance(name, str) or not name:
        return []
    results = _run_pymorphy3_container(lang, [name])
    # results is list of lists; take first element
    if results and isinstance(results[0], list):
        return results[0]
    return []


def extract_base_names_bulk(lang: str, *names: str) -> list[list[str]]:
    """Batch variant: returns a list where each item corresponds to input name's base forms."""
    return _run_pymorphy3_container(lang, list(names))
