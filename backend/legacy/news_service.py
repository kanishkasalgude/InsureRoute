"""
news_service.py — AI Intelligence Brief Generator for InsureRoute.

Generates route-specific intelligence briefs using Google Gemini REST API.
Context includes origin, destination, route path, live weather (Pune-Mumbai),
monsoon/perishable flags, and current risk level.
"""

import os
import time
import hashlib
import json
import logging
from core.gemini_guard import call_gemini_with_guard

logger = logging.getLogger("insure_route.news")

try:
    try:
        from env_loader import load_insure_route_env
    except ImportError:
        from backend.env_loader import load_insure_route_env
    load_insure_route_env()
except ImportError:
    pass

try:
    import requests as _requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

_API_BASE   = "https://generativelanguage.googleapis.com/v1beta/models"
_MODEL_NAME = "gemini-2.5-flash"
_CACHE_TTL  = 300    # 5 minutes per route
_MAX_TOKENS = 600

_cache: dict = {}

_SYSTEM_PROMPT = (
    "You are the InsureRoute Intelligence Engine — a real-time logistics terminal "
    "similar to a Bloomberg terminal for supply chain. "
    "Generate a professional, punchy 'Route Intelligence Brief' based STRICTLY on the "
    "live route data provided below. DO NOT invent fake incidents.\n\n"
    "Rules:\n"
    "- Generate exactly 4 short intelligence alerts.\n"
    "- Each alert is a single line, max 120 characters.\n"
    "- Alerts must reference the actual route (origin → destination).\n"
    "- If live weather data is available for this route, use it factually.\n"
    "- If weather is simulated (non-Pune-Mumbai route), make data-driven inferences "
    "  based on the risk score, monsoon flag, and perishable cargo status.\n"
    "- Return ONLY the 4 alert lines, nothing else."
)


def _fingerprint(context: dict) -> str:
    """Route-aware cache key: different routes get different caches."""
    key = {
        "origin":      context.get("origin", ""),
        "destination": context.get("destination", ""),
        "risk_bucket": round(context.get("risk_pct", 0) / 10) * 10,  # bucket to 10%
        "is_disrupted": context.get("is_disrupted", False),
        "monsoon":     context.get("monsoon", False),
        "perishable":  context.get("perishable", False),
        # Include weather fingerprint only if live checkpoints are present
        "weather_hash": _weather_hash(context.get("live_checkpoints", [])),
    }
    return hashlib.md5(json.dumps(key, sort_keys=True).encode()).hexdigest()


def _weather_hash(checkpoints: list) -> str:
    if not checkpoints:
        return "no-live-weather"
    key = [
        f"{cp.get('name')}:{cp.get('is_dangerous')}:{cp.get('rain_1h')}:{cp.get('wind_speed')}"
        for cp in checkpoints
    ]
    return hashlib.md5(json.dumps(key).encode()).hexdigest()[:8]


def _is_pune_mumbai_route(context: dict) -> bool:
    """True if the route includes the Pune-Mumbai corridor (live weather available)."""
    origin = context.get("origin", "")
    destination = context.get("destination", "")
    path = context.get("path_names", [])
    pune_mumbai_nodes = {"Pune_Hub", "Mumbai_Hub", "Navi_Mumbai_DC", "Nashik_Hub"}
    all_nodes = set(path) | {origin, destination}
    return len(all_nodes & pune_mumbai_nodes) >= 2


def _build_route_prompt(context: dict) -> str:
    origin      = context.get("origin", "Unknown").replace("_", " ").replace(" Hub", "").replace(" DC", "")
    destination = context.get("destination", "Unknown").replace("_", " ").replace(" Hub", "").replace(" DC", "")
    path_names  = context.get("path_names", [origin, destination])
    risk_pct    = context.get("risk_pct", 0)
    is_disrupted = context.get("is_disrupted", False)
    monsoon     = context.get("monsoon", False)
    perishable  = context.get("perishable", False)
    live_checkpoints = context.get("live_checkpoints", [])
    distance_km = context.get("distance_km", 0)
    travel_hrs  = context.get("travel_hrs", 0)

    # Format path for display
    path_display = " → ".join(
        n.replace("_Hub", "").replace("_DC", "").replace("_", " ")
        for n in path_names
    )

    lines = [
        _SYSTEM_PROMPT,
        "",
        "--- ROUTE CONTEXT ---",
        f"ACTIVE ROUTE: {origin} → {destination}",
        f"FULL PATH: {path_display}",
        f"DISTANCE: {distance_km} km | EST. TRAVEL TIME: {travel_hrs} hrs",
        f"DISRUPTION STATUS: {'ACTIVE — rerouting engaged' if is_disrupted else 'NOMINAL'}",
        f"CURRENT RISK SCORE: {risk_pct}%",
        f"MONSOON CONDITIONS: {'Yes' if monsoon else 'No'}",
        f"CARGO TYPE: {'Perishable — time-sensitive' if perishable else 'Standard — non-perishable'}",
    ]

    # Live weather section — only if Pune-Mumbai corridor is in path
    if _is_pune_mumbai_route(context) and live_checkpoints:
        lines.append("")
        lines.append("--- LIVE SENSOR DATA (Pune-Mumbai Corridor) ---")
        overall_dangerous = any(cp.get("is_dangerous") for cp in live_checkpoints)
        lines.append(f"CORRIDOR STATUS: {'DANGEROUS' if overall_dangerous else 'CLEAR'}")
        for cp in live_checkpoints:
            lines.append(
                f"  • {cp.get('name')} ({cp.get('role', '')}): "
                f"Temp {cp.get('temperature', '?')}°C, "
                f"Rain {cp.get('rain_1h', 0):.1f}mm/hr, "
                f"Wind {cp.get('wind_speed', 0):.1f}m/s, "
                f"{' [DANGEROUS]' if cp.get('is_dangerous') else ''}"
            )
    else:
        lines.append("")
        lines.append("--- ROUTE CONDITIONS (Simulated Telemetry) ---")
        lines.append(
            f"No live sensors on this corridor. Use risk score ({risk_pct}%), "
            f"monsoon flag, and cargo type to infer route-specific intelligence."
        )

    lines.append("")
    lines.append("Now generate exactly 4 route intelligence alerts:")
    return "\n".join(lines)


def _call_gemini(api_key: str, prompt: str) -> str:
    def _request():
        url = f"{_API_BASE}/{_MODEL_NAME}:generateContent"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "maxOutputTokens": _MAX_TOKENS,
                "temperature": 0.45,
            },
        }
        resp = _requests.post(url, params={"key": api_key}, json=payload, timeout=35)
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()

    result = call_gemini_with_guard(prompt, _request)
    if isinstance(result, dict) and result.get("fallback"):
        return result["text"]
    return result


def get_route_news(context: dict) -> dict:
    """
    Generate an AI-synthesized route intelligence brief.

    Args:
        context: dict with keys: origin, destination, path_names, live_checkpoints,
                 distance_km, travel_hrs, risk_pct, anomaly_score, monsoon,
                 perishable, is_disrupted
    """
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()

    origin = context.get("origin", "Unknown")
    destination = context.get("destination", "Unknown")

    if not REQUESTS_AVAILABLE or not api_key:
        return {
            "briefs": ["Intelligence feed offline: Missing API Key or requests module."],
            "cached": False,
            "route": f"{origin} → {destination}",
        }

    fp  = _fingerprint(context)
    now = time.monotonic()

    # Cache hit
    if fp in _cache and (now - _cache[fp]["ts"]) < _CACHE_TTL:
        result = dict(_cache[fp]["result"])
        result["cached"] = True
        return result

    # Cache miss — call Gemini
    try:
        prompt = _build_route_prompt(context)
        text   = _call_gemini(api_key, prompt)

        # Parse into list, filter empty lines
        briefs = [line.strip() for line in text.split("\n") if line.strip()]

        # Ensure we have no more than 5 (trim if Gemini is generous)
        briefs = briefs[:5]

        result = {
            "available": True,
            "briefs":    briefs,
            "cached":    False,
            "route":     f"{origin} → {destination}",
        }

        _cache[fp] = {"ts": now, "result": result}

        # Cleanup stale cache entries
        stale = [k for k, v in _cache.items() if now - v["ts"] >= _CACHE_TTL]
        for k in stale:
            del _cache[k]

        origin_label = origin.replace("_Hub", "").replace("_", " ")
        dest_label   = destination.replace("_Hub", "").replace("_", " ")
        print(f"[InsureRoute] Intelligence brief generated for {origin_label}→{dest_label} (key=...{api_key[-6:]})")
        return result

    except Exception as exc:
        logger.error("News Service Gemini API error: %s", exc)
        return {
            "briefs": [f"Intelligence feed temporarily unavailable: {str(exc)[:120]}"],
            "cached": False,
            "route": f"{origin} → {destination}",
        }
