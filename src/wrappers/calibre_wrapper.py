from src.wrappers import docker_wrapper


def convert_book(
    input_name,
    output_name,
    cwd=None,
    cover=None,
    author=None,
    title=None,
    capture_output=True,
    start_reading_at=None,
):
    """
    Convert an input book file to the desired output format using Calibre's ebook-convert.

    Notes:
    - This function DOES NOT create a cover. Pass an already prepared cover file path via `cover`.
    - Prefer running ebook-convert inside a Calibre Docker container; falls back to local binary.
    - Paths (input/output/cover) may be relative to `cwd`.
    """
    base_command = ["ebook-convert", input_name, output_name]

    if cover:
        base_command += ["--cover", cover]
    if author:
        base_command += ["--authors", author]
    if title:
        base_command += ["--title", title.replace("__", " - ").replace("_", " ")]

    if output_name.split(".")[-1] in ["mobi"]:
        base_command += ["--share-not-sync"]
        base_command += ["--mobi-file-type=both"]
        base_command += ["--dont-compress"]
    if output_name.split(".")[-1] in ["mobi", "epub"] and input_name.split(".")[-1] == "html":
        base_command += ["--level1-toc", "//h:h1", "--level2-toc", "//h:h2"]
    if (
        output_name.split(".")[-1] == "mobi"
        and input_name.split(".")[-1] == "html"
        and start_reading_at
    ):
        base_command += ["--start-reading-at", start_reading_at]

    result = docker_wrapper.run_docker_container("calibre", base_command)

    if result.returncode != 0:
        print(result.stderr)
        print(result.stdout)
        raise Exception(result.stderr or "")
    return output_name
