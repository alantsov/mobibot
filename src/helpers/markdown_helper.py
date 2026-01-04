import markdown

from src.helpers.filepath_helper import get_abs_path


def markdown_to_html(file_path):
    with open(get_abs_path(file_path), encoding="utf-8") as f:
        md_text = f.read()
    title = ""
    try:
        title = md_text.strip("\n").split("\n")[0].split("Title: ")[1].strip()
        md_text = "\n".join(md_text.strip("\n").split("\n")[1:])
    except Exception:
        print("no title")
    html = markdown.markdown(md_text, extensions=["markdown.extensions.fenced_code", "tables"])
    html = (
        f"<html><head><title>{title}</title><meta charset='utf-8'></head><body>"
        f"<h1>{title}</h1>"
        f"{html}</body></html>"
    )
    with open(get_abs_path(file_path + ".html"), "w", encoding="utf-8") as f:
        f.write(html)
    return file_path + ".html"
