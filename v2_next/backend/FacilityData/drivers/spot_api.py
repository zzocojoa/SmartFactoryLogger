import asyncio
import re
import threading
import time
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

import httpx

from backend import config

_ACTUATOR_LOCK = threading.Lock()

# 이미지 프록시 단기 캐시
_img_cache: Dict[str, Any] = {"data": None, "time": 0.0, "temp": 0.0, "temp_time": 0.0}
_IMG_CACHE_TTL_SEC = 2.0
_IMG_BACKOFF_BASE_SEC = 0.5
_IMG_BACKOFF_MAX_SEC = 5.0
_TEMP_CACHE_TTL_SEC = 15.0
_SPOT_FOCUS_MIN_MM = 300
_SPOT_FOCUS_MAX_MM = 10000
_img_fetch_lock = asyncio.Lock()
_img_last_error = 0.0
_img_failure_count = 0
_img_cache_state = "empty"
_img_last_cache_log_at = 0.0
_img_last_error_code: Optional[str] = None
_img_last_error_message: Optional[str] = None
_img_next_retry_at: Optional[float] = None
_temp_last_error = 0.0
_temp_last_error_code: Optional[str] = None
_temp_last_error_message: Optional[str] = None
_temp_last_upstream_status: Optional[int] = None
_temp_last_url: Optional[str] = None
_temp_last_success_at = 0.0
_INVALID_IMAGE_PAYLOAD_REJECTION_CODES = {"empty-body", "invalid-image-html", "invalid-image-payload"}

# 연결 풀 재사용을 위한 비동기 HTTP 클라이언트
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


class SpotTemperatureConfigError(ValueError):
    def __init__(self, temp_url: str) -> None:
        super().__init__("SPOT_URL is not configured")
        self.temp_url = temp_url


class SpotTemperatureFetchError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        temp_url: str,
        upstream_status: Optional[int],
    ) -> None:
        super().__init__(message)
        self.code = code
        self.temp_url = temp_url
        self.upstream_status = upstream_status


class SpotFocusControlError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        focus_url: str,
        upstream_status: Optional[int],
    ) -> None:
        super().__init__(message)
        self.focus_url = focus_url
        self.upstream_status = upstream_status


def _format_exception_message(exc: BaseException) -> str:
    message = str(exc).strip()
    if message:
        return message
    return exc.__class__.__name__


def _response_body_preview(response: httpx.Response, max_chars: int) -> str:
    body = response.text.strip()
    if len(body) <= max_chars:
        return body
    return body[:max_chars]


def _response_content_type(response: httpx.Response) -> str:
    return str(response.headers.get("content-type") or "").strip()


def _image_payload_type(data: bytes) -> Optional[str]:
    if data.startswith(b"\xff\xd8") and data.endswith(b"\xff\xd9"):
        return "jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
        return "gif"
    if data.startswith(b"BM"):
        return "bmp"
    if len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "webp"
    return None


def _payload_looks_like_html(data: bytes) -> bool:
    sample = data.lstrip()[:256].lower()
    return (
        sample.startswith(b"<!doctype html")
        or sample.startswith(b"<html")
        or sample.startswith(b"<head")
        or sample.startswith(b"<body")
        or b"<html" in sample[:80]
    )


def _is_spot_image_payload_rejection_code(error_code: str | None) -> bool:
    if error_code is None:
        return False
    return error_code in _INVALID_IMAGE_PAYLOAD_REJECTION_CODES


def _validate_spot_image_response(response: httpx.Response, image_url: str, data: bytes) -> None:
    content_type = _response_content_type(response)
    if _payload_looks_like_html(data):
        raise SpotImageFetchError(
            "invalid-image-html",
            (
                "SPOT image upstream returned HTML instead of image bytes; "
                f"url={image_url}; status_code={response.status_code}; "
                f"content_type={content_type}; body={_response_body_preview(response, 200)}"
            ),
            image_url=image_url,
            upstream_status=response.status_code,
        )
    if _image_payload_type(data) is None:
        raise SpotImageFetchError(
            "invalid-image-payload",
            (
                "SPOT image upstream returned a non-image payload; "
                f"url={image_url}; status_code={response.status_code}; "
                f"content_type={content_type}; body={_response_body_preview(response, 200)}"
            ),
            image_url=image_url,
            upstream_status=response.status_code,
        )


def _resolve_spot_image_url() -> str:
    image_url = str(config.SPOT_IMAGE_URL or "").strip()
    if not image_url:
        raise SpotImageConfigError(image_url)
    return image_url


def _resolve_spot_image_url_candidates(image_url: str) -> list[str]:
    stripped_url = image_url.rstrip("/")
    try:
        parsed = urlsplit(stripped_url)
    except Exception as exc:
        raise SpotImageFetchError(
            "upstream-request-error",
            (
                "SPOT image upstream URL is malformed; "
                f"url={image_url}; error={_format_exception_message(exc)}"
            ),
            image_url=image_url,
            upstream_status=None,
        ) from exc

    if not parsed.scheme or not parsed.netloc:
        return [image_url]

    normalized_path = (parsed.path or "").rstrip("/")
    if not normalized_path:
        return [image_url]

    normalized_lower = normalized_path.lower()
    variant_paths: list[str] = []
    if normalized_lower.endswith("/image"):
        variant_paths.append(normalized_path + ".jpg")
    elif normalized_lower.endswith("/image.jpg"):
        variant_paths.append(normalized_path[:-4])
    elif normalized_lower.endswith("/image.jpeg"):
        variant_paths.append(normalized_path[:-5])
    elif normalized_lower.endswith("/image.png"):
        variant_paths.append(normalized_path[:-4])

    candidates = [image_url]
    for variant_path in variant_paths:
        if variant_path == normalized_path:
            continue
        candidates.append(parsed._replace(path=variant_path).geturl())
    seen: list[str] = []
    for candidate in candidates:
        if candidate not in seen:
            seen.append(candidate)
    return seen


def _is_retryable_spot_image_error(error: SpotImageFetchError, has_next_candidate: bool) -> bool:
    if not has_next_candidate:
        return False
    if error.code == "upstream-http-error":
        return error.upstream_status == 404
    if error.code in {"invalid-image-html", "invalid-image-payload"}:
        return True
    return False


def _resolve_spot_temperature_url() -> str:
    temp_url = str(config.SPOT_URL or "").strip()
    if not temp_url:
        raise SpotTemperatureConfigError(temp_url)
    return temp_url


async def _request_spot_image_from_url(client: httpx.AsyncClient, image_url: str) -> bytes:
    try:
        response = await client.get(image_url)
        response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise SpotImageFetchError(
            "upstream-timeout",
            (
                "SPOT image upstream timed out; "
                f"url={image_url}; error_type={exc.__class__.__name__}; "
                f"error={_format_exception_message(exc)}"
            ),
            image_url=image_url,
            upstream_status=None,
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise SpotImageFetchError(
            "upstream-http-error",
            (
                f"SPOT image upstream returned HTTP {exc.response.status_code}; "
                f"url={image_url}; body={_response_body_preview(exc.response, 200)}"
            ),
            image_url=image_url,
            upstream_status=exc.response.status_code,
        ) from exc
    except httpx.RequestError as exc:
        raise SpotImageFetchError(
            "upstream-request-error",
            (
                "SPOT image upstream request failed; "
                f"url={image_url}; error_type={exc.__class__.__name__}; "
                f"error={_format_exception_message(exc)}"
            ),
            image_url=image_url,
            upstream_status=None,
        ) from exc

    data = response.content
    if not data:
        raise SpotImageFetchError(
            "empty-body",
            f"SPOT image upstream returned an empty body; url={image_url}",
            image_url=image_url,
            upstream_status=response.status_code,
        )
    _validate_spot_image_response(response, image_url, data)
    return data


async def _request_spot_image(client: httpx.AsyncClient, image_url: str) -> bytes:
    from ...MESSync.logger import get_logger

    logger = get_logger("spot_control")
    candidates = _resolve_spot_image_url_candidates(image_url)
    if len(candidates) == 1:
        return await _request_spot_image_from_url(client, candidates[0])

    last_error: Optional[SpotImageFetchError] = None
    for index, candidate in enumerate(candidates):
        try:
            payload = await _request_spot_image_from_url(client, candidate)
            if index > 0:
                logger.warning(
                    "SPOT image endpoint fallback succeeded",
                    extra={
                        "configured_image_url": image_url,
                        "resolved_image_url": candidate,
                        "attempted_paths": candidates,
                    },
                )
            return payload
        except SpotImageFetchError as exc:
            last_error = exc
            if _is_retryable_spot_image_error(exc, index < len(candidates) - 1):
                logger.warning(
                    "SPOT image endpoint candidate failed",
                    extra={
                        "configured_image_url": image_url,
                        "attempted_image_url": candidate,
                        "next_candidate": candidates[index + 1],
                        "attempt": index + 1,
                        "max_attempts": len(candidates),
                        "error_code": exc.code,
                        "upstream_status": exc.upstream_status,
                    },
                )
                continue
            break

    if last_error is None:
        last_error = SpotImageFetchError(
            "upstream-request-error",
            "SPOT image upstream failed for all configured endpoint candidates",
            image_url=image_url,
            upstream_status=None,
        )
    raise last_error


async def _request_spot_temperature(client: httpx.AsyncClient, temp_url: str) -> float:
    try:
        response = await client.get(temp_url)
        response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise SpotTemperatureFetchError(
            "temperature-upstream-timeout",
            (
                "SPOT temperature upstream timed out; "
                f"url={temp_url}; error_type={exc.__class__.__name__}; "
                f"error={_format_exception_message(exc)}"
            ),
            temp_url=temp_url,
            upstream_status=None,
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise SpotTemperatureFetchError(
            "temperature-upstream-http-error",
            (
                f"SPOT temperature upstream returned HTTP {exc.response.status_code}; "
                f"url={temp_url}; body={_response_body_preview(exc.response, 200)}"
            ),
            temp_url=temp_url,
            upstream_status=exc.response.status_code,
        ) from exc
    except httpx.RequestError as exc:
        raise SpotTemperatureFetchError(
            "temperature-upstream-request-error",
            (
                "SPOT temperature upstream request failed; "
                f"url={temp_url}; error_type={exc.__class__.__name__}; "
                f"error={_format_exception_message(exc)}"
            ),
            temp_url=temp_url,
            upstream_status=None,
        ) from exc

    raw_temp = response.text.strip()
    if not raw_temp:
        raise SpotTemperatureFetchError(
            "temperature-empty-body",
            f"SPOT temperature upstream returned an empty body; url={temp_url}",
            temp_url=temp_url,
            upstream_status=response.status_code,
        )

    try:
        return float(raw_temp)
    except ValueError as exc:
        raise SpotTemperatureFetchError(
            "temperature-parse-error",
            (
                "SPOT temperature upstream returned a non-numeric body; "
                f"url={temp_url}; body={raw_temp[:200]}"
            ),
            temp_url=temp_url,
            upstream_status=response.status_code,
        ) from exc


def _record_image_error(code: str, message: str) -> None:
    global _img_last_error
    global _img_last_error_code
    global _img_last_error_message

    _img_last_error = time.time()
    _img_last_error_code = code
    _img_last_error_message = message


def _record_image_success() -> None:
    global _img_failure_count
    global _img_last_error_code
    global _img_last_error_message
    global _img_next_retry_at

    _img_failure_count = 0
    _img_last_error_code = None
    _img_last_error_message = None
    _img_next_retry_at = None


def _record_image_backoff(backoff_sec: float) -> None:
    global _img_next_retry_at

    if backoff_sec <= 0.0:
        _img_next_retry_at = None
        return
    _img_next_retry_at = time.time() + backoff_sec


def _record_temperature_error(
    code: str,
    message: str,
    temp_url: str,
    upstream_status: Optional[int],
) -> None:
    global _temp_last_error
    global _temp_last_error_code
    global _temp_last_error_message
    global _temp_last_upstream_status
    global _temp_last_url

    _temp_last_error = time.time()
    _temp_last_error_code = code
    _temp_last_error_message = message
    _temp_last_upstream_status = upstream_status
    _temp_last_url = temp_url


def _record_temperature_success(temp_url: str) -> None:
    global _temp_last_error_code
    global _temp_last_error_message
    global _temp_last_upstream_status
    global _temp_last_url
    global _temp_last_success_at

    _temp_last_error_code = None
    _temp_last_error_message = None
    _temp_last_upstream_status = None
    _temp_last_url = temp_url
    _temp_last_success_at = time.time()


def _temperature_cache_age_sec(now: float) -> Optional[float]:
    temp_time = float(_img_cache.get("temp_time") or 0.0)
    if temp_time <= 0.0:
        return None
    return max(0.0, now - temp_time)


def _temperature_cache_status(now: float) -> str:
    age = _temperature_cache_age_sec(now)
    if age is None:
        if _temp_last_error_code:
            return "error"
        return "empty"
    if age > _TEMP_CACHE_TTL_SEC:
        return "stale"
    return "ok"


async def _refresh_spot_temperature(client: httpx.AsyncClient) -> None:
    temp_url = _resolve_spot_temperature_url()
    temperature = await _request_spot_temperature(client, temp_url)
    _img_cache["temp"] = temperature
    _img_cache["temp_time"] = time.time()
    _record_temperature_success(temp_url)


def get_image_proxy_diagnostics() -> Dict[str, Any]:
    now = time.time()
    cache_age = _cache_age_sec(now) if _img_cache["data"] else None
    cache_status = _cache_status(now)
    retry_after = _retry_after_sec(now)
    return {
        "cache_state": _cache_state_for_status(cache_status),
        "cache_status": cache_status,
        "image_status": _image_status_for_cache_status(cache_status),
        "proxy_state": _image_proxy_state(now),
        "last_cache_state": str(_img_cache_state),
        "failure_count": int(_img_failure_count),
        "last_error_at": float(_img_last_error) if _img_last_error else None,
        "last_error_code": _img_last_error_code,
        "last_error_message": _img_last_error_message,
        "image_url_configured": bool(str(config.SPOT_IMAGE_URL or "").strip()),
        "has_cached_image": bool(_img_cache["data"]),
        "cache_captured_at": float(_img_cache.get("time") or 0.0) if _img_cache["data"] else None,
        "cache_age_sec": cache_age,
        "max_stale_age_sec": _max_stale_age_sec(),
        "current_backoff_sec": _current_backoff_sec(),
        "next_retry_at": _img_next_retry_at,
        "retry_after_sec": retry_after,
        "temperature_url_configured": bool(str(config.SPOT_URL or "").strip()),
        "temperature_cache_status": _temperature_cache_status(now),
        "temperature_cache_age_sec": _temperature_cache_age_sec(now),
        "temperature_last_success_at": float(_temp_last_success_at) if _temp_last_success_at else None,
        "temperature_last_error_at": float(_temp_last_error) if _temp_last_error else None,
        "temperature_last_error_code": _temp_last_error_code,
        "temperature_last_error_message": _temp_last_error_message,
        "temperature_last_upstream_status": _temp_last_upstream_status,
        "temperature_last_url": _temp_last_url,
    }


def _get_http_client() -> httpx.AsyncClient:
    """공유 비동기 HTTP 클라이언트를 지연 초기화해 반환한다."""
    global _http_client
    if _http_client is None:
        timeout = httpx.Timeout(
            connect=1.0,
            # 응답 대기 제한을 5초로 둔다.
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


def _cache_status(now: float) -> str:
    if not _img_cache["data"]:
        return "empty"
    if _cache_age_sec(now) >= _max_stale_age_sec():
        return "stale"
    return "fresh"


def _cache_state_for_status(cache_status: str) -> str:
    if cache_status == "fresh":
        return "cache"
    return cache_status


def _image_status_for_cache_status(cache_status: str) -> str:
    if cache_status == "fresh":
        return "ok"
    return cache_status


def _retry_after_sec(now: float) -> Optional[float]:
    if _img_next_retry_at is None or _img_failure_count <= 0:
        return None
    return max(0.0, _img_next_retry_at - now)


def _image_proxy_state(now: float) -> str:
    retry_after = _retry_after_sec(now)
    if retry_after is not None and retry_after > 0.0:
        return "backoff"
    if _img_last_error_code:
        return "error"
    return "ok"


def _build_image_meta(now: float, status: str, source: str) -> Dict[str, Any]:
    captured_at = float(_img_cache.get("time") or 0.0)
    cache_status = _cache_status(now)
    return {
        "status": status,
        "source": source,
        "captured_at": captured_at,
        "age_sec": _cache_age_sec(now),
        "cache_status": cache_status,
        "proxy_state": _image_proxy_state(now),
        "failure_count": int(_img_failure_count),
        "last_error_code": _img_last_error_code,
        "max_stale_age_sec": _max_stale_age_sec(),
        "next_retry_at": _img_next_retry_at,
        "retry_after_sec": _retry_after_sec(now),
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
        cache_status = _cache_status(now)
        status = _image_status_for_cache_status(cache_status)
        next_cache_state = _cache_state_for_status(cache_status)
        if _img_cache_state != next_cache_state and _should_log_cache_state(now):
            if next_cache_state == "cache":
                logger.info("Spot cache serve: age_sec=%.3f", age)
            else:
                logger.warning("Spot stale serve: age_sec=%.3f", age)
        _img_cache_state = next_cache_state
        return _img_cache["data"], _build_image_meta(now, status, next_cache_state)
    
    # 캐시가 비어있으면 초기 로드를 위해 한 번 직접 가져온다.
    try:
        image_url = _resolve_spot_image_url()
    except SpotImageConfigError as exc:
        _record_image_error("config-missing", str(exc))
        raise
    
    async with _img_fetch_lock:
        # 잠금 획득 후 캐시를 다시 확인한다.
        if _img_cache["data"]:
            cached_now = time.time()
            cached_age = _cache_age_sec(cached_now)
            cached_cache_status = _cache_status(cached_now)
            cached_status = _image_status_for_cache_status(cached_cache_status)
            next_cache_state = _cache_state_for_status(cached_cache_status)
            _img_cache_state = next_cache_state
            return _img_cache["data"], _build_image_meta(cached_now, cached_status, next_cache_state)
        
        client = _get_http_client()
        try:
            data = await _request_spot_image(client, image_url)
        except SpotImageFetchError as exc:
            if _is_spot_image_payload_rejection_code(exc.code):
                raise
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
            client = _get_http_client()
            if config.SPOT_IMAGE_URL:
                image_url = _resolve_spot_image_url()
                data = await _request_spot_image(client, image_url)

                if data:
                    _img_cache["data"] = data
                    _img_cache["time"] = time.time()
                    _img_cache_state = "upstream"
                    if _img_failure_count > 0:
                        logger.info(
                            "Spot image fetch recovered",
                            extra={"failure_count": _img_failure_count},
                        )
                    _img_failure_count = 0
                    _record_image_success()

            if config.SPOT_URL:
                try:
                    await _refresh_spot_temperature(client)
                except SpotTemperatureConfigError as exc:
                    _record_temperature_error("temperature-config-missing", str(exc), exc.temp_url, None)
                    logger.warning(
                        "Spot temperature fetch misconfigured",
                        extra={
                            "code": "temperature-config-missing",
                            "temp_url": exc.temp_url,
                            "error": str(exc),
                        },
                    )
                except SpotTemperatureFetchError as exc:
                    _record_temperature_error(exc.code, str(exc), exc.temp_url, exc.upstream_status)
                    logger.warning(
                        "Spot temperature fetch failed",
                        extra={
                            "code": exc.code,
                            "temp_url": exc.temp_url,
                            "upstream_status": exc.upstream_status,
                            "error": str(exc),
                        },
                    )
                    
        except asyncio.CancelledError:
            break
        except SpotImageConfigError as exc:
            _record_image_error("config-missing", str(exc))
            _img_failure_count = min(_img_failure_count + 1, 10)
            config_backoff = max(interval, 1.0)
            _record_image_backoff(config_backoff)
            logger.warning(
                "Spot image fetch misconfigured",
                extra={
                    "code": "config-missing",
                    "error": str(exc),
                    "failure_count": _img_failure_count,
                    "next_backoff_sec": config_backoff,
                    "next_retry_at": _img_next_retry_at,
                },
            )
            await asyncio.sleep(config_backoff)
            next_tick = time.time()
        except SpotImageFetchError as exc:
            if _is_spot_image_payload_rejection_code(exc.code):
                continue
            _record_image_error(exc.code, str(exc))
            _img_failure_count = min(_img_failure_count + 1, 10)
            backoff = _current_backoff_sec()
            _record_image_backoff(backoff)
            if _img_failure_count == 1 or _img_failure_count >= 6:
                logger.warning(
                    "Spot image fetch failed",
                    extra={
                        "code": exc.code,
                        "error": str(exc),
                        "failure_count": _img_failure_count,
                        "next_backoff_sec": backoff,
                        "next_retry_at": _img_next_retry_at,
                        "image_url": exc.image_url,
                        "upstream_status": exc.upstream_status,
                    },
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
            # 작업이 너무 오래 걸려 다음 실행 시점을 이미 지난 경우 보정한다.
            next_tick = now
            await asyncio.sleep(0.1) # 최소 0.1초 휴식으로 프로세서 점유 방지


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
    # 이미지가 너무 오래되었거나(15초), 온도가 없으면 0.0 반환
    if not _img_cache["temp_time"] or (now - _img_cache["temp_time"] > _TEMP_CACHE_TTL_SEC):
        return 0.0
    return _img_cache["temp"]


def _resolve_spot_focus_url() -> str:
    focus_url = str(config.SPOT_FOCUS_URL or "").strip()
    if not focus_url:
        raise RuntimeError("SPOT_FOCUS_URL is not configured")
    return focus_url


def _preview_spot_focus_body(content: bytes) -> str:
    return content.decode("utf-8", errors="replace").strip()[:200]


def _decode_spot_focus_body(content: bytes, focus_url: str, upstream_status: Optional[int]) -> str:
    try:
        return content.decode("utf-8", errors="strict").strip()
    except UnicodeDecodeError as exc:
        raise SpotFocusControlError(
            "SPOT focus response is not UTF-8; "
            f"url={focus_url}; status_code={upstream_status}; body={_preview_spot_focus_body(content)}",
            focus_url=focus_url,
            upstream_status=upstream_status,
        ) from exc


def _parse_spot_focus_position(
    raw_focus: str,
    focus_url: str,
    upstream_status: Optional[int],
) -> int:
    if not re.fullmatch(r"\d+", raw_focus):
        raise SpotFocusControlError(
            "SPOT focus response is not an integer; "
            f"url={focus_url}; status_code={upstream_status}; body={raw_focus[:200]}",
            focus_url=focus_url,
            upstream_status=upstream_status,
        )
    return int(raw_focus)


def _raise_spot_focus_request_error(action: str, focus_url: str, exc: BaseException) -> None:
    raise SpotFocusControlError(
        "SPOT focus request failed; "
        f"action={action}; url={focus_url}; error_type={exc.__class__.__name__}; "
        f"error={_format_exception_message(exc)}",
        focus_url=focus_url,
        upstream_status=None,
    ) from exc


def _read_spot_focus_position(focus_url: str) -> int:
    try:
        with urlopen(focus_url, timeout=3) as resp:
            code = resp.getcode()
            content = resp.read()
    except HTTPError as exc:
        body = _preview_spot_focus_body(exc.read())
        raise SpotFocusControlError(
            f"SPOT focus read failed: HTTP {exc.code}; url={focus_url}; body={body[:200]}",
            focus_url=focus_url,
            upstream_status=exc.code,
        ) from exc
    except (TimeoutError, URLError, ValueError) as exc:
        _raise_spot_focus_request_error("read", focus_url, exc)

    if code != 200:
        raise SpotFocusControlError(
            f"SPOT focus read failed: HTTP {code}; url={focus_url}; body={_preview_spot_focus_body(content)}",
            focus_url=focus_url,
            upstream_status=code,
        )

    raw_focus = _decode_spot_focus_body(content, focus_url, code)
    return _parse_spot_focus_position(raw_focus, focus_url, code)


def _write_spot_focus_position(focus_url: str, new_val: int) -> None:
    request = Request(
        focus_url,
        data=str(new_val).encode("ascii"),
        headers={"Content-Type": "text/plain"},
        method="PUT",
    )
    try:
        with urlopen(request, timeout=3) as resp:
            code = resp.getcode()
            content = resp.read()
    except HTTPError as exc:
        body = _preview_spot_focus_body(exc.read())
        raise SpotFocusControlError(
            "SPOT focus write failed: "
            f"HTTP {exc.code}; url={focus_url}; value={new_val}; body={body[:200]}",
            focus_url=focus_url,
            upstream_status=exc.code,
        ) from exc
    except (TimeoutError, URLError, ValueError) as exc:
        _raise_spot_focus_request_error("write", focus_url, exc)

    if code != 200:
        raise SpotFocusControlError(
            f"SPOT focus write failed: HTTP {code}; url={focus_url}; "
            f"value={new_val}; body={_preview_spot_focus_body(content)}",
            focus_url=focus_url,
            upstream_status=code,
        )
    raw_focus = _decode_spot_focus_body(content, focus_url, code)
    written_value = _parse_spot_focus_position(raw_focus, focus_url, code)
    if written_value != new_val:
        raise SpotFocusControlError(
            "SPOT focus write returned unexpected value; "
            f"url={focus_url}; status_code={code}; value={new_val}; body={raw_focus[:200]}",
            focus_url=focus_url,
            upstream_status=code,
        )


def move_focus(steps: int) -> Dict[str, Any]:
    if steps == 0:
        return {"status": "noop", "message": "steps=0"}

    focus_url = _resolve_spot_focus_url()

    with _ACTUATOR_LOCK:
        current = _read_spot_focus_position(focus_url)
        delta = steps * max(1, config.SPOT_FOCUS_STEP)
        new_val = current + delta

        # v1 동작에 맞춰 범위를 제한한다.
        new_val = max(_SPOT_FOCUS_MIN_MM, min(_SPOT_FOCUS_MAX_MM, new_val))
        if new_val == current:
            return {
                "status": "limit",
                "current": current,
                "new": new_val,
                "request_steps": steps,
                "focus_step": config.SPOT_FOCUS_STEP,
            }

        _write_spot_focus_position(focus_url, new_val)

        return {
            "status": "ok",
            "current": current,
            "new": new_val,
            "request_steps": steps,
            "focus_step": config.SPOT_FOCUS_STEP,
        }
