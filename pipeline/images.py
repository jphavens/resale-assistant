"""Image loading for vision calls: HEIC support, downscale, base64 JPEG encode.

All formats normalize to JPEG so every pipeline step sends a uniform
media_type regardless of what the phone shot (HEIC, PNG, JPEG).
"""
from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path

import pillow_heif
from PIL import Image, ImageOps

pillow_heif.register_heif_opener()

MAX_LONG_EDGE = 1568
JPEG_QUALITY = 85


def load_image_as_api_content_block(path: Path, max_long_edge: int = MAX_LONG_EDGE) -> dict:
    """Load an image (JPEG/PNG/HEIC), downscale to control token cost, and
    return an Anthropic vision content block.
    """
    image = Image.open(path)
    image = ImageOps.exif_transpose(image)
    image = image.convert("RGB")

    width, height = image.size
    scale = max_long_edge / max(width, height)
    if scale < 1:
        image = image.resize((round(width * scale), round(height * scale)), Image.LANCZOS)

    buf = BytesIO()
    image.save(buf, format="JPEG", quality=JPEG_QUALITY)
    encoded = base64.standard_b64encode(buf.getvalue()).decode("utf-8")

    return {
        "type": "image",
        "source": {"type": "base64", "media_type": "image/jpeg", "data": encoded},
    }
