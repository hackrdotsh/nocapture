import os
import tempfile
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps


def compose_window(
    source: Path, destination: Path, wallpaper: Path | None, shadow: bool, padding: int
) -> None:
    if not 0 <= padding <= 512:
        raise ValueError("Padding must be between 0 and 512 pixels.")
    with Image.open(source) as image:
        window = ImageOps.exif_transpose(image).convert("RGBA")
    margin = max(padding, 72 if shadow else 0)
    size = (window.width + 2 * margin, window.height + 2 * margin)
    canvas = Image.new("RGBA", size)
    if wallpaper is not None:
        with Image.open(wallpaper) as background:
            canvas = ImageOps.fit(ImageOps.exif_transpose(background).convert("RGBA"), size)
    if shadow:
        alpha = Image.new("L", size)
        alpha.paste(window.getchannel("A"), (margin, margin + 14))
        alpha = alpha.filter(ImageFilter.GaussianBlur(20)).point(lambda value: value * 0.38)
        shade = Image.new("RGBA", size, "black")
        shade.putalpha(alpha)
        canvas = Image.alpha_composite(canvas, shade)
    canvas.alpha_composite(window, (margin, margin))
    atomic_png(canvas, destination)


def atomic_png(image: Image.Image, destination: Path) -> None:
    descriptor, name = tempfile.mkstemp(suffix=".png", dir=destination.parent)
    os.close(descriptor)
    temporary = Path(name)
    try:
        image.save(temporary, format="PNG")
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def gif_command(source: Path, destination: Path, fps: int, width: int) -> list[str]:
    if not 1 <= fps <= 30 or not 16 <= width <= 3840:
        raise ValueError("GIF frame rate must be 1–30 and width must be 16–3840.")
    filters = (
        f"fps={fps},scale=w='min({width},iw)':h=-2:flags=lanczos,split[a][b];"
        "[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=sierra2_4a"
    )
    return [
        "ffmpeg",
        "-nostdin",
        "-v",
        "error",
        "-y",
        "-i",
        str(source),
        "-filter_complex",
        filters,
        "-an",
        "-loop",
        "0",
        str(destination),
    ]
