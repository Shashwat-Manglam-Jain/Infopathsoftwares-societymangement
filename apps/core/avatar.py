import hashlib
import io

from PIL import Image, ImageDraw, ImageFont

AVATAR_COLORS = [
    (239, 68, 68),  # red
    (249, 115, 22),  # orange
    (234, 179, 8),  # yellow
    (34, 197, 94),  # green
    (6, 182, 212),  # cyan
    (59, 130, 246),  # blue
    (139, 92, 246),  # violet
    (236, 72, 153),  # pink
    (168, 85, 247),  # purple
    (20, 184, 166),  # teal
]


def _get_color(name: str) -> tuple:
    h = int(hashlib.md5(name.encode()).hexdigest(), 16)
    return AVATAR_COLORS[h % len(AVATAR_COLORS)]


def _get_initials(name: str) -> str:
    parts = name.strip().split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()
    if parts:
        return parts[0][0].upper()
    return '?'


def generate_avatar(name: str, size: int = 128) -> bytes:
    bg = _get_color(name)
    img = Image.new('RGB', (size, size), bg)
    draw = ImageDraw.Draw(img)

    initials = _get_initials(name)
    font_size = size // 2

    try:
        font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', font_size)
    except OSError:
        try:
            font = ImageFont.truetype('/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf', font_size)
        except OSError:
            font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), initials, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (size - tw) / 2 - bbox[0]
    y = (size - th) / 2 - bbox[1]
    draw.text((x, y), initials, fill=(255, 255, 255), font=font)

    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()
