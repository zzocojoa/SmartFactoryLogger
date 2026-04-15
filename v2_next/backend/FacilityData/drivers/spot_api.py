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
_img_cache_state = "empty"
_img_last_cache_log_at = 0.0
_img_last_error_code: Optional[str] = None
_img_last_error_message: Optional[str] = None

# Async HTTP client (reused for connection pooling)
_http_client: Optional[httpx.AsyncClient] = None


class SpotImageConfigError(ValueError):
    def __init__(self, image_url: str) -> None:
        super().__init__("SPOT_IMAGE_URL is not configured")
        self.image_url = image_url


class SpotImageFetchError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        image_url: str,
        upstream_status: Optional[int],
    ) -> None:
        super().__init__(message)
        self.code = code
        self.image_url = image_url
        self.upstream_status = upstream_status


def _resolve_spot_image_url() -> str:
    image_url = str(config.SPOT_IMAGE_URL or "").strip()
    if not image_url:
        raise SpotImageConfigError(image_url)
    return image_url


async def _request_spot_image(client: httpx.AsyncClient, image_url: str) -> bytes:
    try:
        response = await client.get(image_url)
        response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise SpotImageFetchError(
            "upstream-timeout",
            "SPOT image upstream timed out",
            image_url=image_url,
            upstream_status=None,
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise SpotImageFetchError(
            "upstream-http-error",
            f"SPOT image upstream returned HTTP {exc.response.status_code}",
            image_url=image_url,
            upstream_status=exc.response.status_code,
        ) from exc
    except httpx.RequestError as exc:
        raise SpotImageFetchError(
            "upstream-request-error",
            f"SPOT image upstream request failed: {exc}",
            image_url=image_url,
            upstream_status=None,
        ) from exc

    data = response.content
    if not data:
        raise SpotImageFetchError(
            "empty-body",
            "SPOT image upstream returned an empty body",
            image_url=image_url,
            upstream_status=response.status_code,
        )
    return data


def _record_image_error(code: str, message: str) -> None:
    global _img_last_error
    global _img_last_error_code
    global _img_last_error_message

    _img_last_error = time.time()
    _img_last_error_code = code
    _img_last_error_message = message


def _record_image_success() -> None:
    global _img_last_error_code
    global _img_last_error_message

    _img_last_error_code = None
    _img_last_error_message = None


def get_image_proxy_diagnostics() -> Dict[str, Any]:
    return {
        "cache_state": str(_img_cache_state),
        "failure_count": int(_img_failure_count),
        "last_error_at": float(_img_last_error) if _img_last_error else None,
        "last_error_code": _img_last_error_code,
        "last_error_message": _img_last_error_message,
        "image_url_configured": bool(str(config.SPOT_IMAGE_URL or "").strip()),
    }


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


def _should_log_cache_state(now: float) -> bool:
    global _img_last_cache_log_at
    if now - _img_last_cache_log_at < 10.0:
        return False
    _img_last_cache_log_at = now
    return True


async def fetch_image_async() -> tuple[bytes, Dict[str, Any]]:
    """캐시에서 즉시 반환 (백그라운드 프리페칭된 이미지)."""
    global _img_cache_state
    from ...MESSync.logger import get_logger

    logger = get_logger("spot_control")
    now = time.time()
    
    # 캐시에 이미지가 있으면 즉시 반환
    if _img_cache["data"]:
        age = _cache_age_sec(now)
        status = "ok" if age < _max_stale_age_sec() else "stale"
        next_cache_state = "cache" if status == "ok" else "stale"
        if _img_cache_state != next_cache_state and _should_log_cache_state(now):
            if next_cache_state == "cache":
                logger.info("Spot cache serve: age_sec=%.3f", age)
            else:
                logger.warning("Spot stale serve: age_sec=%.3f", age)
        _img_cache_state = next_cache_state
        return _img_cache["data"], _build_image_meta(now, status, next_cache_state)
    
    # 캐시가 비어있으면 한번 직접 fetch 시도 (초기 로드용)
    image_url = _resolve_spot_image_url()
    
    async with _img_fetch_lock:
        # Double-check after lock
        if _img_cache["data"]:
            cached_now = time.time()
            cached_age = _cache_age_sec(cached_now)
            cached_status = "ok" if cached_age < _max_stale_age_sec() else "stale"
            next_cache_state = "cache" if cached_status == "ok" else "stale"
            _img_cache_state = next_cache_state
            return _img_cache["data"], _build_image_meta(cached_now, cached_status, next_cache_state)
        
        client = _get_http_client()
        try:
            data = await _request_spot_image(client, image_url)
        except SpotImageFetchError as exc:
            _record_image_error(exc.code, str(exc))
            raise
        _img_cache["data"] = data
        _img_cache["time"] = time.time()
        _img_cache_state = "upstream"
        _record_image_success()
        return data, _build_image_meta(time.time(), "ok", "upstream")


# --- 백그라운드 프리페칭 ---
_prefetch_task: Optional[asyncio.Task] = None
_prefetch_running = False


async def _prefetch_loop():
    """백그라운드에서 지속적으로 SPOT 이미지 프리페칭 (드리프트 방지 로직 적용)."""
    global _img_cache_state, _img_failure_count, _img_last_error, _prefetch_running
    _prefetch_running = True
    
    from ...MESSync.logger import get_logger
    logger = get_logger("spot_control")
    
    interval = max(0.5, float(config.SPOT_REFRESH_INTERVAL or 1.0))
    next_tick = time.time()
    
    while _prefetch_running:
        try:
            if config.SPOT_IMAGE_URL:
                client = _get_http_client()
                image_url = _resolve_spot_image_url()
                data = await _request_spot_image(client, image_url)

                if data:
                    _img_cache["data"] = data
                    _img_cache["time"] = time.time()
                    _img_cache_state = "upstream"
                    if _img_failure_count > 0:
                        logger.info("Spot image fetch recovered after %s failures", _img_failure_count)
                    _img_failure_count = 0
                    _record_image_success()

                if config.SPOT_URL:
                    try:
                        temp_resp = await client.get(config.SPOT_URL)
                        temp_resp.raise_for_status()
                        raw_temp = temp_resp.text.strip()
                        if raw_temp:
                            _img_cache["temp"] = float(raw_temp)
                            _img_cache["temp_time"] = time.time()
                    except ValueError as exc:
                        logger.warning("Spot temperature parse failed: %s", exc)
                    except Exception as exc:
                        logger.warning("Spot temperature fetch failed: %s", exc)
                    
        except asyncio.CancelledError:
            break
        except SpotImageConfigError as exc:
            _record_image_error("config-missing", str(exc))
            _img_failure_count = min(_img_failure_count + 1, 10)
            logger.warning(
                "Spot image fetch misconfigured: error=%s failure_count=%s",
                str(exc),
                _img_failure_count,
            )
            await asyncio.sleep(max(interval, 1.0))
            next_tick = time.time()
        except SpotImageFetchError as exc:
            _record_image_error(exc.code, str(exc))
            _img_failure_count = min(_img_failure_count + 1, 10)
            backoff = _current_backoff_sec()
            if _img_failure_count == 1 or _img_failure_count >= 6:
                logger.warning(
                    "Spot image fetch failed: code=%s error=%s failure_count=%s next_backoff_sec=%.1f",
                    exc.code,
                    str(exc),
                    _img_failure_count,
                    backoff,
                )
            
            if backoff > 0:
                await asyncio.sleep(backoff)
                next_tick = time.time()
        except Exception as exc:
            _record_image_error("unknown", str(exc))
            _img_failure_count = min(_img_failure_count + 1, 10)
            backoff = _current_backoff_sec()
            logger.warning(
                "Spot image fetch failed: code=%s error=%s failure_count=%s next_backoff_sec=%.1f",
                "unknown",
                str(exc),
                _img_failure_count,
                backoff,
            )
            if backoff > 0:
                await asyncio.sleep(backoff)
                next_tick = time.time()
        
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
