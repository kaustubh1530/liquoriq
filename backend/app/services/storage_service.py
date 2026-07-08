"""
services/storage_service.py — Image storage abstraction (Phase 11)

One interface, two backends:
  - Local disk  (dev default)      → saved to settings.creatives_dir,
                                     served at /static/creatives/<name>.png
  - Cloudinary  (prod, when set)   → permanent CDN URL (https://res.cloudinary.com/...)

Why an abstraction instead of calling Cloudinary directly from creative_service?
  1. Dev works offline with zero setup.
  2. Swapping to S3 later = one file changes.
  3. Railway's disk is ephemeral — Cloudinary fixes "images vanish on redeploy".

Config: set CLOUDINARY_URL env var (cloudinary://<api_key>:<api_secret>@<cloud_name>)
to activate the Cloudinary backend. Empty = local disk.

Note on async: the cloudinary SDK is synchronous (blocking HTTP). We run its
calls in a thread via asyncio.to_thread so we never block FastAPI's event loop.
"""

import asyncio
import logging
import uuid
from pathlib import Path

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_CLOUDINARY_ENABLED = bool(settings.cloudinary_url)

if _CLOUDINARY_ENABLED:
    import cloudinary
    import cloudinary.uploader

    # cloudinary:// URL carries cloud_name + key + secret in one string
    cloudinary.config(cloudinary_url=settings.cloudinary_url, secure=True)
    # warning level so it's visible in default (unconfigured) logging, same as the JWT line
    logger.warning("Storage backend: Cloudinary")
else:
    logger.warning("Storage backend: local disk (%s)", settings.creatives_dir)


async def save_image(png_bytes: bytes, prefix: str = "ad") -> str:
    """
    Persist PNG bytes, return the URL to serve them from.

    Local:      /static/creatives/<prefix>-<uuid>.png   (relative)
    Cloudinary: https://res.cloudinary.com/.../<id>.png (absolute, permanent CDN)
    """
    name = f"{prefix}-{uuid.uuid4().hex}"

    if _CLOUDINARY_ENABLED:
        def _upload() -> str:
            result = cloudinary.uploader.upload(
                png_bytes,
                public_id=name,
                folder="liquoriq/creatives",
                resource_type="image",
                format="png",
            )
            return result["secure_url"]

        url = await asyncio.to_thread(_upload)
        logger.info("Uploaded to Cloudinary: %s", url)
        return url

    # Local disk
    creatives_dir = Path(settings.creatives_dir)
    creatives_dir.mkdir(parents=True, exist_ok=True)
    (creatives_dir / f"{name}.png").write_bytes(png_bytes)
    return f"/static/creatives/{name}.png"


async def fetch_image(image_url: str) -> bytes:
    """
    Read an image back as bytes, whichever backend it lives on.
    Needed by compose_service: the overlay is drawn on the ORIGINAL background.

    Raises ValueError if the image can't be retrieved (e.g. local file wiped
    by a Railway redeploy before Cloudinary was enabled → user regenerates).
    """
    if image_url.startswith("http"):
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(image_url)
            if resp.status_code != 200:
                raise ValueError(f"Could not fetch image ({resp.status_code}): {image_url}")
            return resp.content

    # Local relative URL: /static/creatives/<name>.png → generated_images/<name>.png
    filename = image_url.rsplit("/", 1)[-1]
    path = Path(settings.creatives_dir) / filename
    if not path.exists():
        raise ValueError(
            "Original image file not found (it may have been cleared on redeploy). "
            "Regenerate the creative first."
        )
    return path.read_bytes()
