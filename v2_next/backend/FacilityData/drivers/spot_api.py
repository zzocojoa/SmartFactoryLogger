import asyncio
import re
import threading
import time
from typing import Any, Dict, Optional
from urllib.request import urlopen

import httpx

from backend import config

_ACTUATOR_LOCK = threading.Lock()
_POS_PATTERN = re.compile(rb"Pos-->\s*(\d+)")

# Short-term cache for image proxy (Throttling)
_img_cache: Dict[str, Any] = {"data": None, "time": 0.0, "temp": 0.0, "temp_time": 0.0}
_IMG_CACHE_TTL_SEC = 2.0
_IMG_BACKOFF_BASE_SEC = 0.5
_IMG_BACKOFF_MAX_SEC = 5.0
_img_fetch_lock = asyncio.Lock()
_img_last_error = 0.0
_img_failure_count = 0

# Async HTTP client (reused for connection pooling)
_http_client: Optional[httpx.AsyncClient] = None


def _get_http_client() -> httpx.AsyncClient:
    """Lazily initialize and return the shared async HTTP client."""
    global _http_client
    if _http_client is None:
        timeout = httpx.Timeout(
            connect=1.0,
            # Increase read timeout to 5s for better resilience globally
            read=5.0, 
            write=1.0,
            pool=5.0,
        )
        _http_client = httpx.AsyncClient(timeout=timeout)
    return _http_client


def _current_backoff_sec() -> float:
    if _img_failure_count <= 0:
        return 0.0
    return min(_IMG_BACKOFF_MAX_SEC, _IMG_BACKOFF_BASE_SEC * (2 ** (_img_failure_count - 1)))


def _max_stale_age_sec() -> float:
    refresh = float(config.SPOT_REFRESH_INTERVAL or 0)
    return max(5.0, refresh * 5.0)


def _cache_age_sec(now: float) -> float:
    return max(0.0, now - float(_img_cache.get("time") or 0.0))


def _build_image_meta(now: float, status: str, source: str) -> Dict[str, Any]:
    captured_at = float(_img_cache.get("time") or 0.0)
    return {
        "status": status,
        "source": source,
        "captured_at": captured_at,
        "age_sec": _cache_age_sec(now),
    }


async def fetch_image_async() -> tuple[bytes, Dict[str, Any]]:
    """캐시에서 즉시 반환 (백그라운드 프리페칭된 이미지)."""
    now = time.time()
    
    # 캐시에 이미지가 있으면 즉시 반환
    if _img_cache["data"]:
        age = _cache_age_sec(now)
        status = "ok" if age < _max_stale_age_sec() else "stale"
        return _img_cache["data"], _build_image_meta(now, status, "cache")
    
    # 캐시가 비어있으면 한번 직접 fetch 시도 (초기 로드용)
    if not config.SPOT_IMAGE_URL:
        raise ValueError("SPOT_IMAGE_URL is not configured")
    
    async with _img_fetch_lock:
        # Double-check after lock
        if _img_cache["data"]:
            return _img_cache["data"], _build_image_meta(time.time(), "ok", "cache")
        
        client = _get_http_client()
        try:
            response = await client.get(config.SPOT_IMAGE_URL)
            response.raise_for_status()
            data = response.content
            if not data:
                raise RuntimeError("Empty SPOT image response")
            
            _img_cache["data"] = data
            _img_cache["time"] = time.time()
            return data, _build_image_meta(time.time(), "ok", "upstream")
        except Exception as exc:
            # First fetch failure is expected if camera is offline
            raise RuntimeError(f"SPOT image fetch failed: {exc}") from exc


# --- 백그라운드 프리페칭 ---
_prefetch_task: Optional[asyncio.Task] = None
_prefetch_running = False


async def _prefetch_loop():
    """백그라운드에서 지속적으로 SPOT 이미지 프리페칭 (드리프트 방지 로직 적용)."""
    global _img_failure_count, _img_last_error, _prefetch_running
    _prefetch_running = True
    
    from ...MESSync.logger import get_logger
    logger = get_logger("spot_control")
    
    interval = max(0.5, float(config.SPOT_REFRESH_INTERVAL or 1.0))
    next_tick = time.time()
    
    while _prefetch_running:
        try:
            if config.SPOT_IMAGE_URL:
                client = _get_http_client()
                response = await client.get(config.SPOT_IMAGE_URL)
                response.raise_for_status()
                data = response.content

                if data:
                    _img_cache["data"] = data
                    _img_cache["time"] = time.time()
                    if _img_failure_count > 0:
                        logger.info(f"Spot image stream reconnected after {_img_failure_count} failures")
                    _img_failure_count = 0

                if config.SPOT_URL:
                    try:
                        temp_resp = await client.get(config.SPOT_URL)
                        temp_resp.raise_for_status()
                        raw_temp = temp_resp.text.strip()
                        if raw_temp:
                            _img_cache["temp"] = float(raw_temp)
                            _img_cache["temp_time"] = time.time()
                    except ValueError as exc:
                        logger.warning(f"Spot temperature parse failed: {exc}")
                    except Exception as exc:
                        logger.warning(f"Spot temperature fetch failed: {exc}")
                    
        except asyncio.CancelledError:
            break
        except Exception as e:
            _img_last_error = time.time()
            _img_failure_count = min(_img_failure_count + 1, 10)
            backoff = _current_backoff_sec()
            if _img_failure_count == 1 or _img_failure_count >= 6:
                 logger.warning(f"Spot image fetch failed: {str(e)} (Count: {_img_failure_count}, Next Backoff: {backoff:.1f}s)")
            
            # 실패 시 백오프 적용
            if backoff > 0:
                await asyncio.sleep(backoff)
                next_tick = time.time() # Reset tick after backoff recovery
        
        # 드리프트 방지: 다음 실행 시간 계산
        next_tick += interval
        now = time.time()
        sleep_time = next_tick - now
        
        if sleep_time > 0:
            await asyncio.sleep(sleep_time)
        else:
            # 작업이 너무 오래 걸려 다음 tick을 이미 지남 -> tick 보정
            next_tick = now
            await asyncio.sleep(0.1) # 최소 0.1초 휴식으로 CPU 점유 방지


async def start_prefetch_loop():
    """백그라운드 프리페칭 시작."""
    global _prefetch_task, _prefetch_running
    if _prefetch_task and not _prefetch_task.done():
        return  # 이미 실행 중
    
    _prefetch_running = True
    _prefetch_task = asyncio.create_task(_prefetch_loop())


async def stop_prefetch_loop():
    """백그라운드 프리페칭 중지."""
    global _prefetch_task, _prefetch_running
    _prefetch_running = False
    
    if _prefetch_task:
        _prefetch_task.cancel()
        try:
            await _prefetch_task
        except asyncio.CancelledError:
            pass
        _prefetch_task = None


def get_cached_spot_temp() -> float:
    """캐시된 SPOT 온도를 반환 (PLC 드라이버 등에서 사용)."""
    now = time.time()
    # 이미지가 너무 오래되었거나(15s), 온도가 없으면 0.0 반환
    if not _img_cache["temp_time"] or (now - _img_cache["temp_time"] > 15.0):
        return 0.0
    return _img_cache["temp"]


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
                "request_steps": steps,
                "actuator_step": config.SPOT_ACTUATOR_STEP,
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
            "request_steps": steps,
            "actuator_step": config.SPOT_ACTUATOR_STEP,
        }
