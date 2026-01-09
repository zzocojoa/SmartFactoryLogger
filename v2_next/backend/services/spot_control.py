import asyncio
import re
import threading
import time
from typing import Any, Dict, Optional
from urllib.request import urlopen

import httpx

from .. import config

_ACTUATOR_LOCK = threading.Lock()
_POS_PATTERN = re.compile(rb"Pos-->\s*(\d+)")

# Short-term cache for image proxy (Throttling)
_img_cache: Dict[str, Any] = {"data": None, "time": 0.0}

# Async HTTP client (reused for connection pooling)
_http_client: Optional[httpx.AsyncClient] = None


def _get_http_client() -> httpx.AsyncClient:
    """Lazily initialize and return the shared async HTTP client."""
    global _http_client
    if _http_client is None:
        timeout = httpx.Timeout(
            connect=1.0,
            read=config.SPOT_TIMEOUT or 2.0,
            write=1.0,
            pool=5.0,
        )
        _http_client = httpx.AsyncClient(timeout=timeout)
    return _http_client


async def fetch_image_async() -> bytes:
    """Fetch image asynchronously with short-term caching (0.5s)."""
    if not config.SPOT_IMAGE_URL:
        raise ValueError("SPOT_IMAGE_URL is not configured")

    now = time.time()
    # 1. Cache Check
    if _img_cache["data"] and (now - _img_cache["time"] < 0.5):
        return _img_cache["data"]

    # 2. Async Fetch (non-blocking)
    client = _get_http_client()
    response = await client.get(config.SPOT_IMAGE_URL)
    response.raise_for_status()
    data = response.content

    # 3. Update Cache
    if data:
        _img_cache["data"] = data
        _img_cache["time"] = now
    return data


def move_focus(steps: int) -> Dict[str, Any]:
    if steps == 0:
        return {"status": "noop", "message": "steps=0"}

    if not config.SPOT_ACTUATOR_URL:
        raise RuntimeError("SPOT_ACTUATOR_URL is not configured")

    with _ACTUATOR_LOCK:
        read_url = f"{config.SPOT_ACTUATOR_URL}?scan=3"
        with urlopen(read_url, timeout=3) as resp:
            content = resp.read()

        match = _POS_PATTERN.search(content)
        if not match:
            raise ValueError("Actuator position not found in response")

        current = int(match.group(1).decode("ascii"))
        delta = steps * max(1, config.SPOT_ACTUATOR_STEP)
        new_val = current + delta

        # Clamp (based on v1 behavior)
        new_val = max(0, min(1000, new_val))
        if new_val == current:
            return {
                "status": "limit",
                "current": current,
                "new": new_val,
                "step": config.SPOT_ACTUATOR_STEP,
            }

        write_url = f"{config.SPOT_ACTUATOR_URL}?scan=3&move={new_val}"
        with urlopen(write_url, timeout=3) as resp:
            code = resp.getcode()

        if code != 200:
            raise RuntimeError(f"Actuator write failed: HTTP {code}")

        return {
            "status": "ok",
            "current": current,
            "new": new_val,
            "step": config.SPOT_ACTUATOR_STEP,
        }
