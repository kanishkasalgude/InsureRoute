import os
import time
import threading
from typing import Any, Callable


RPM_LIMIT = int(os.getenv("GEMINI_RPM", "15"))
DAILY_LIMIT = int(os.getenv("GEMINI_DAILY_LIMIT", "1400"))
MIN_INTERVAL_SECONDS = 4.0
CACHE_TTL_SECONDS = 300

_cache: dict[str, tuple[float, Any]] = {}
_daily_count = 0
_daily_window_start = time.time()
_last_call_at = 0.0
_lock = threading.Lock()


def _roll_daily_window(now: float) -> None:
    global _daily_window_start, _daily_count
    if now - _daily_window_start >= 86400:
        _daily_window_start = now
        _daily_count = 0


def call_gemini_with_guard(prompt: str, call_fn: Callable[[], Any], retries: int = 3) -> Any:
    """
    Guard Gemini calls with:
    - prompt-level cache (5 min TTL)
    - global min spacing between calls (4s)
    - per-day request cap
    - bounded retry loop
    """
    global _daily_count, _last_call_at

    key = prompt.strip().lower()
    now = time.time()

    with _lock:
        _roll_daily_window(now)

        if key in _cache and (now - _cache[key][0]) < CACHE_TTL_SECONDS:
            return _cache[key][1]

        if _daily_count >= DAILY_LIMIT:
            return {
                "text": "Fallback response (API limit reached)",
                "fallback": True,
            }

        elapsed = now - _last_call_at
        if elapsed < MIN_INTERVAL_SECONDS:
            time.sleep(MIN_INTERVAL_SECONDS - elapsed)

    last_error = None
    for attempt in range(retries):
        try:
            result = call_fn()
            with _lock:
                _daily_count += 1
                _last_call_at = time.time()
                _cache[key] = (time.time(), result)
            return result
        except Exception as exc:  # noqa: BLE001 - caller handles surfaced error
            last_error = exc
            if attempt < retries - 1:
                time.sleep(1)

    raise last_error
