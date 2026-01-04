import os

from PIL import Image, ImageDraw, ImageFont

from src.helpers.filepath_helper import generate_random_filename


def crop_by_bbox(image_filepath: str, bbox: list[int], index) -> str:
    image = Image.open(image_filepath)
    w, h = image.size
    xmin_pct, ymin_pct, xmax_pct, ymax_pct = bbox

    # Convert percentage bbox → pixel coordinates
    left = int(xmin_pct * w / 1000)
    top = int(ymin_pct * h / 1000)
    right = int(xmax_pct * w / 1000)
    bottom = int(ymax_pct * h / 1000)
    save_path = f"{image_filepath}_{index}.jpg"
    cropped = image.crop((left, top, right, bottom))
    cropped.save(save_path)
    return save_path


def wrap_title(title: str) -> list[str]:
    title = (title or " ").replace("_", " ")
    words = [w for w in title.split(" ") if w]
    if not words:
        return []
    lines = [words[0]]
    for w in words[1:]:
        if len(lines[-1] + " " + w) <= 20:
            lines[-1] += " " + w
        else:
            lines.append(w)
    return lines


def create_cover(base_image_path, title, author, cwd=None):
    """
    Local wrapper around Pillow cover creation.
    - Runs directly in Python using Pillow.
    - Uses Pillow's built-in default font to avoid any system or external dependencies.
    - If `cwd` is provided: output file is written there; returned path is relative to `cwd`.
    - If `cwd` is None: uses the project's 'data' directory and prefixes the returned path with 'data/'.
    """
    base_image_path = base_image_path or "/dev/null"
    # Prepare output filename (relative to workdir)
    output_name = generate_random_filename("new_cover_image", "jpg")

    # Determine host workdir and ensure it exists
    if cwd:
        host_workdir = os.path.abspath(cwd)
        os.makedirs(host_workdir, exist_ok=True)
        output_path = os.path.join(host_workdir, output_name)
        base_image_path = os.path.join(host_workdir, base_image_path)
        returned_path = output_name
    else:
        data_dir = os.path.abspath("data")
        os.makedirs(data_dir, exist_ok=True)
        output_path = os.path.join(data_dir, output_name)
        base_image_path = os.path.join(data_dir, base_image_path)
        returned_path = f"data/{output_name}"

    # Local cover creation logic (adapted from create_cover_internal)
    width, height = 1600, 2560
    cover = Image.new("RGB", (width, height), (255, 255, 255))

    # Load base image (handle if it's /dev/null or missing)
    try:
        base_image = Image.open(base_image_path)
        base_image = base_image.resize((width - 200, height // 2), Image.Resampling.LANCZOS)
    except (FileNotFoundError, OSError):
        base_image = Image.new("RGB", (width, height), (255, 255, 255))  # Blank fallback

    base_x = (width - base_image.width) // 2
    base_y = (height - base_image.height) // 2
    if base_image.mode in ("RGBA", "LA"):
        mask = base_image.convert("RGBA").split()[3]
        cover.paste(base_image, (base_x, base_y), mask)
    else:
        cover.paste(base_image, (base_x, base_y))

    draw = ImageDraw.Draw(cover)

    # Use Pillow's built-in default font (no external files or system packages)
    # Note: If using Pillow <10.0, size is ignored and font is small; upgrade if needed.
    try:
        title_font = ImageFont.truetype("DejaVuSans.ttf", size=150)
        author_font = ImageFont.truetype("DejaVuSans.ttf", size=120)
    except TypeError:  # Fallback for older Pillow versions (no size param)
        title_font = ImageFont.load_default()
        author_font = ImageFont.load_default()

    author = (author or " ")[:18] or " "
    title_lines = wrap_title(title)  # Assume wrap_title is defined elsewhere or implement it

    # Title placement
    margin_top = 100
    # Measure a single line height based on a representative string
    bbox = draw.textbbox((0, 0), title_lines[0] if title_lines else "", font=title_font)
    _, _, w0, h0 = bbox if bbox else (0, 0, 0, 0)
    line_h = h0 or 150
    for i, line in enumerate(title_lines[:2]):
        tb = draw.textbbox((0, 0), line, font=title_font)
        tw = (tb[2] - tb[0]) if tb else 0
        tx = (width - tw) // 2
        ty = int(margin_top + i * line_h * 1.3)
        draw.text((tx, ty), line, fill="black", font=title_font)

    # Author at the bottom
    ab = draw.textbbox((0, 0), author, font=author_font)
    aw = (ab[2] - ab[0]) if ab else 0
    ah = (ab[3] - ab[1]) if ab else 0
    ax = (width - aw) // 2
    ay = height - ah - 100
    draw.text((ax, ay), author, fill="black", font=author_font)

    cover.save(output_path)
    return returned_path
