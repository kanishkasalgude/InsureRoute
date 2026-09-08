"""
gemini_advisor.py — Google Gemini AI Risk Advisor for InsureRoute.

Uses the Gemini REST API directly via requests (no SDK dependency).
This avoids all SDK versioning and API-version issues.

Optimisations

1. No SDK – plain HTTP POST to the REST endpoint, zero SDK overhead.
2. Server-side cache – 60-second TTL based on context fingerprint.
3. Compact prompt – ~150 input tokens.
4. Token cap – maxOutputTokens: 256.
"""

import os
import time
import hashlib
import json
import logging
from core.gemini_guard import call_gemini_with_guard

logger = logging.getLogger("insure_route.gemini")

#  Load .env from repo root and backend/.env 
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
    logger.warning("requests not installed — AI advisor disabled")

#  Configuration 
# REST endpoint — v1beta is the standard Gemini API version
_API_BASE   = "https://generativelanguage.googleapis.com/v1beta/models"
_MODEL_NAME = "gemini-2.5-flash"
_CACHE_TTL  = 60    # seconds
_MAX_TOKENS = 256

#  In-process response cache 
_cache: dict = {}

#  System + prompt 
_SYSTEM_PROMPT = (
    "You are InsureRoute AI, a concise logistics risk advisor. "
    "Analyse the shipment snapshot below and reply EXACTLY in this format:\n"
    "SUMMARY: <2-3 sentences>\n"
    "ACTIONS:\n- <action1>\n- <action2>\n- <action3>\n"
    "INSURANCE_TIP: <one tip>\n"
    "Use only the numbers provided. No extra commentary.\n\n"
)


#  Context fingerprint 
def _fingerprint(context: dict) -> str:
    ins   = context.get("insurance", {})
    route = context.get("route", {})
    kpis  = context.get("kpis", {})
    key = {
        "disrupted":  route.get("disruption_detected", False),
        "rerouted":   route.get("rerouted", False),
        "risk":       round(float(kpis.get("risk", 0)), 1),
        "prob":       round(float(ins.get("disruption_probability", 0)), 2),
        "wx_mult":    round(float(ins.get("weather_multiplier", 1.0)), 1),
        "src":        context.get("trigger_source", ""),
        "monsoon":    context.get("flags", {}).get("monsoon", False),
        "perishable": context.get("flags", {}).get("perishable", False),
    }
    return hashlib.md5(json.dumps(key, sort_keys=True).encode()).hexdigest()


#  Compact prompt builder 
def _build_prompt(context: dict) -> str:
    ins   = context.get("insurance", {})
    route = context.get("route", {})
    kpis  = context.get("kpis", {})
    flags = context.get("flags", {})
    wx    = context.get("weather", {})

    disrupted = route.get("disruption_detected", False)
    path = "→".join(route.get("path", []))

    lines = [
        _SYSTEM_PROMPT,
        f"Route: {route.get('origin','?')}→{route.get('destination','?')} ({path})",
        f"Rerouted:{route.get('rerouted',False)} Dist:{route.get('total_distance_km','?')}km",
        f"AnomalyScore:{context.get('anomaly_score','?')} Disrupted:{disrupted}",
        f"RiskProb:{round(ins.get('disruption_probability', 0) * 100, 1)}%",
        f"SLA:{kpis.get('sla',0)}% Delay:{kpis.get('delay',0)}% Risk:{kpis.get('risk',0)}%",
        f"Cargo:INR{ins.get('cargo_value',0):,.0f} Premium:INR{ins.get('base_premium',0):,.0f}",
        f"HedgeBefore:INR{ins.get('before_cost',0):,.0f} HedgeAfter:INR{ins.get('after_cost',0):,.0f}",
        f"Savings:INR{ins.get('savings',0):,.0f}({ins.get('savings_pct',0)}%)",
        f"WxMult:{ins.get('weather_multiplier',1.0)}x PerishMult:{ins.get('perishable_multiplier',1.0)}x",
        f"Monsoon:{flags.get('monsoon',False)} Perishable:{flags.get('perishable',False)}",
        f"Trigger:{context.get('trigger_source','?')}",
    ]

    if wx.get("is_dangerous"):
        lines += [
            f"WEATHER ALERT at {wx.get('disruption_point','?')}: {wx.get('reason','?')}",
            f"Severity:{wx.get('severity',0)} AltRoute:Bhiwandi",
        ]

    return "\n".join(lines)


#  Response parser 
def _parse(text: str) -> tuple:
    summary, actions, tip = "", [], ""
    section = None
    for line in text.split("\n"):
        s = line.strip()
        up = s.upper()
        if up.startswith("SUMMARY:"):
            section = "summary"; summary = s[8:].strip()
        elif up.startswith("ACTIONS:"):
            section = "actions"
        elif up.startswith("INSURANCE_TIP:"):
            section = "tip"; tip = s[14:].strip()
        elif section == "summary" and s:
            summary += " " + s
        elif section == "actions" and s.startswith("-"):
            actions.append(s.lstrip("- ").strip())
        elif section == "tip" and s:
            tip += " " + s
    return summary or text[:300], actions[:4], tip


#  REST call 
def _call_gemini(api_key: str, prompt: str) -> str:
    """POST to the Gemini REST API and return the generated text."""
    def _request():
        url = f"{_API_BASE}/{_MODEL_NAME}:generateContent"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "maxOutputTokens": _MAX_TOKENS,
                "temperature": 0.3,
            },
        }
        resp = _requests.post(
            url,
            params={"key": api_key},
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()

    result = call_gemini_with_guard(prompt, _request)
    if isinstance(result, dict) and result.get("fallback"):
        return result["text"]
    return result


#  Public API 
def get_ai_advisory(context: dict) -> dict:
    """
    Return a cached advisory if available, otherwise call the Gemini REST API.
    Results are cached for CACHE_TTL seconds (60 s).
    """
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()

    if not REQUESTS_AVAILABLE or not api_key:
        return {
            "available":     False,
            "summary":       "AI advisor unavailable — GEMINI_API_KEY not configured.",
            "actions":       [],
            "insurance_tip": "",
            "model":         None,
            "cached":        False,
        }

    fp  = _fingerprint(context)
    now = time.monotonic()

    #  Cache hit 
    if fp in _cache and (now - _cache[fp]["ts"]) < _CACHE_TTL:
        result = dict(_cache[fp]["result"])
        result["cached"] = True
        return result

    #  Cache miss → REST call 
    try:
        prompt  = _build_prompt(context)
        text    = _call_gemini(api_key, prompt)

        summary, actions, tip = _parse(text)

        result = {
            "available":     True,
            "summary":       summary,
            "actions":       actions,
            "insurance_tip": tip,
            "model":         _MODEL_NAME,
            "cached":        False,
        }

        _cache[fp] = {"ts": now, "result": result}
        stale = [k for k, v in _cache.items() if now - v["ts"] >= _CACHE_TTL]
        for k in stale:
            del _cache[k]

        print(f"[InsureRoute] Gemini advisory generated (key=...{api_key[-6:]})")
        return result

    except Exception as exc:
        logger.error("Gemini REST API error: %s", exc)
        return {
            "available":     False,
            "summary":       f"AI advisor temporarily unavailable: {str(exc)[:200]}",
            "actions":       [],
            "insurance_tip": "",
            "model":         _MODEL_NAME,
            "cached":        False,
        }
