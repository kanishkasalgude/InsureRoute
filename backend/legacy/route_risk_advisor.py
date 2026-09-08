"""
route_risk_advisor.py — Advanced AI Route Risk Advisor for InsureRoute.

Generates a full structured risk analysis for ANY source → destination route.
Uses the Google Gemini REST API with a rich prompt that requests:
  1. Route Summary
  2. Segment-wise analysis (traffic, weather, road risks, safety rating, advice)
  3. Critical segment identification
  4. Smart recommendations
  5. Live intelligence status

Works for:
  - Pune-Mumbai: uses real OWM live weather checkpoint data
  - Any other route: uses graph engine path + seeded simulation weather
"""

import os
import time
import hashlib
import json
import logging
from core.gemini_guard import call_gemini_with_guard

logger = logging.getLogger("insure_route.route_risk_advisor")

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
    logger.warning("requests not installed — Route Risk Advisor disabled")

#  Configuration 
_API_BASE   = "https://generativelanguage.googleapis.com/v1beta/models"
_MODEL_NAME = "gemini-2.5-flash"
_CACHE_TTL  = 60     # seconds
_MAX_TOKENS = 2500   # full detailed analysis — raised for segment coverage

#  In-process response cache 
_cache: dict = {}


#  System Prompt 
_SYSTEM_PROMPT = """You are InsureRoute AI, a real-world intelligent navigation risk advisor.

Generate a DETAILED, STRUCTURED risk analysis for the route provided.
Use EXACTLY this section format (keep each segment analysis brief — 1 line per bullet):

## ROUTE SUMMARY
- Total Distance: <X km>
- Estimated Travel Time: <X hrs X min>
- Key Segments: <ghat / expressway / urban zones — 1 line>
- Route Type: <National Highway / Expressway / Mixed>

## SEGMENT ANALYSIS
<For EACH checkpoint listed in the data, write one block:>

### [Exact Checkpoint Name]
- Traffic Status: <Light / Moderate / Heavy>
- Weather Conditions: <brief — e.g., Clear skies / Light rain / Dense fog>
- Road Risks: <brief — e.g., Sharp curves, Landslide-prone, Urban congestion>
- Safety Rating: <Low Risk / Moderate Risk / High Risk>
- Advice: <One specific action — e.g., Slow to 40 km/h, Use fog lights>

## CRITICAL SEGMENT
- Name: <most dangerous checkpoint name from the list above>
- Reason: <2-3 sentences explaining the hazard>
- Delay Probability: <X%>
- Hazard Type: <primary hazard label>

## SMART RECOMMENDATIONS
- Best Travel Time: <time window>
- Speed Advisory: <e.g., Limit to 60 km/h on ghat sections>
- Precautions: <key safety measure>
- Alternate Route: <if any; else say 'No alternate recommended'>
- Fuel/Rest Stop: <1 suggested stop>

## LIVE STATUS
- Overall Route Status: <Green - Safe / Moderate - Exercise Caution / Dangerous - High Alert>
- Quick Decision: <One sentence — proceed, delay, or reroute>

IMPORTANT: You MUST write a ### segment block for EVERY checkpoint in the data. Be concise per bullet (max 15 words). Do not skip any checkpoint."""


#  Checkpoint data builder 
def _build_checkpoint_section(checkpoints: list) -> str:
    """Format checkpoint data into a readable prompt section."""
    if not checkpoints:
        return "No real-time checkpoint data available."
    lines = []
    for cp in checkpoints:
        name     = cp.get("name", "Unknown")
        role     = cp.get("role", "mid_route").replace("_", " ")
        rain     = cp.get("rain_1h", 0)
        wind     = cp.get("wind_speed", 0)
        temp     = cp.get("temperature", 25)
        humidity = cp.get("humidity", 60)
        desc     = cp.get("description", "clear")
        severity = cp.get("severity", 0)
        danger   = cp.get("is_dangerous", False)

        status = "DANGEROUS" if danger else ("MODERATE" if severity > 0.2 else "CLEAR")
        lines.append(
            f"  - {name} ({role}): {desc} | Rain: {rain}mm/hr | Wind: {wind}m/s | "
            f"Temp: {temp}°C | Humidity: {humidity}% | Severity: {severity} | {status}"
        )
    return "\n".join(lines)


#  Prompt builder 
def _build_prompt(context: dict) -> str:
    origin      = context.get("origin", "Origin")
    destination = context.get("destination", "Destination")
    checkpoints = context.get("checkpoints", [])
    distance_km = context.get("distance_km", "N/A")
    travel_hrs  = context.get("travel_hrs", "N/A")
    risk_pct    = context.get("risk_pct", 0)
    anomaly     = context.get("anomaly_score", 0)
    monsoon     = context.get("monsoon", False)
    cargo_type  = context.get("cargo_type", "Standard")
    is_disrupted = context.get("is_disrupted", False)
    data_source  = context.get("data_source", "simulated")
    path_names   = context.get("path_names", [])

    # Format origin/destination for display
    orig_label = origin.replace("_", " ").replace(" Hub", "").replace(" DC", "")
    dest_label = destination.replace("_", " ").replace(" Hub", "").replace(" DC", "")

    checkpoint_text = _build_checkpoint_section(checkpoints)
    path_str = " → ".join(p.replace("_", " ").replace(" Hub", "").replace(" DC", "") for p in path_names) if path_names else f"{orig_label} → {dest_label}"

    lines = [
        _SYSTEM_PROMPT,
        "",
        "=== ROUTE INPUT DATA ===",
        f"Source: {orig_label}",
        f"Destination: {dest_label}",
        f"Route Path: {path_str}",
        f"Estimated Distance: {distance_km} km",
        f"Estimated Travel Time: {travel_hrs} hrs",
        f"Number of Checkpoints: {len(checkpoints)}",
        f"ML Risk Probability: {risk_pct}%",
        f"Anomaly Score: {anomaly}",
        f"Monsoon Season Active: {monsoon}",
        f"Cargo Type: {cargo_type} (Evaluate risk specifically for this cargo!)",
        f"Disruption Detected: {is_disrupted}",
        f"Weather Data Source: {data_source}",
        "",
        "=== LIVE CHECKPOINT DATA ===",
        checkpoint_text,
        "",
        "=== YOUR TASK ===",
        "Generate the full route risk analysis in the exact format specified above.",
        "Each segment in the SEGMENT ANALYSIS section must correspond to an actual checkpoint above.",
        f"Generate analysis for ALL {len(checkpoints)} checkpoints listed.",
    ]

    return "\n".join(lines)


#  Cache fingerprint 
def _fingerprint(context: dict) -> str:
    key = {
        "origin":      context.get("origin"),
        "destination": context.get("destination"),
        "is_disrupted": context.get("is_disrupted"),
        "risk_pct":    round(float(context.get("risk_pct", 0)), 1),
        "checkpoints": [
            f"{c.get('name')}:{c.get('is_dangerous')}:{round(float(c.get('rain_1h', 0)), 1)}"
            for c in context.get("checkpoints", [])
        ],
    }
    return hashlib.md5(json.dumps(key, sort_keys=True).encode()).hexdigest()


#  REST call 
def _call_gemini(api_key: str, prompt: str) -> str:
    def _request():
        url = f"{_API_BASE}/{_MODEL_NAME}:generateContent"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "maxOutputTokens": _MAX_TOKENS,
                "temperature": 0.35,
            },
        }
        resp = _requests.post(url, params={"key": api_key}, json=payload, timeout=45)
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()

    result = call_gemini_with_guard(prompt, _request)
    if isinstance(result, dict) and result.get("fallback"):
        return result["text"]
    return result


#  Response parser 
def _parse_response(text: str) -> dict:
    """
    Parse the structured Gemini response into a JSON-serialisable dict.
    Handles markdown variations: ## Section, **## Section**, etc.
    """
    sections = {
        "route_summary":      "",
        "segment_analysis":   "",
        "segments":           [],
        "critical_segment":   {},
        "recommendations":    "",
        "live_status":        "",
        "overall_status":     "Moderate",
        "quick_decision":     "",
        "raw_text":           text,
    }

    current_section = None
    current_segment = None
    segment_buffer  = {}

    def _clean(s):
        """Strip markdown bold/italic markers for header detection."""
        return s.replace('**', '').replace('*', '').replace('__', '').strip()

    for line in text.split("\n"):
        stripped = line.strip()
        cleaned  = _clean(stripped).upper()

        #  Section headers 
        if cleaned.startswith("## ROUTE SUMMARY"):
            current_section = "route_summary"
            current_segment = None
            continue
        elif cleaned.startswith("## SEGMENT ANALYSIS"):
            current_section = "segment_analysis"
            current_segment = None
            continue
        elif cleaned.startswith("## CRITICAL SEGMENT"):
            if current_segment and segment_buffer:
                sections["segments"].append(dict(segment_buffer))
                segment_buffer = {}
                current_segment = None
            current_section = "critical_segment"
            continue
        elif cleaned.startswith("## SMART RECOMMENDATIONS"):
            current_section = "recommendations"
            continue
        elif cleaned.startswith("## LIVE STATUS"):
            current_section = "live_status"
            continue

        #  Sub-section: individual segment 
        if current_section == "segment_analysis" and _clean(stripped).startswith("### "):
            if current_segment and segment_buffer:
                sections["segments"].append(dict(segment_buffer))
            seg_name = _clean(stripped)[4:].strip().lstrip('[').rstrip(']')
            current_segment = seg_name
            segment_buffer = {
                "name":          seg_name,
                "traffic":       "Moderate",
                "weather":       "—",
                "road_risks":    "—",
                "safety_rating": "Moderate Risk",
                "advice":        "—",
            }
            sections["segment_analysis"] += f"\n### {seg_name}\n"
            continue

        #  Skip blank lines 
        if not stripped:
            if current_section in ("route_summary", "segment_analysis", "recommendations", "live_status"):
                sections[current_section] += "\n"
            continue

        #  Content routing 
        if current_section == "route_summary":
            sections["route_summary"] += stripped + "\n"

        elif current_section == "segment_analysis":
            sections["segment_analysis"] += stripped + "\n"
            if current_segment and stripped.startswith("- "):
                content = stripped[2:]
                cl = content.lower()
                if cl.startswith("traffic status:"):
                    segment_buffer["traffic"] = content[15:].strip()
                elif cl.startswith("weather conditions:"):
                    segment_buffer["weather"] = content[19:].strip()
                elif cl.startswith("road risks:"):
                    segment_buffer["road_risks"] = content[11:].strip()
                elif cl.startswith("safety rating:"):
                    segment_buffer["safety_rating"] = content[14:].strip()
                elif cl.startswith("advice:"):
                    segment_buffer["advice"] = content[7:].strip()

        elif current_section == "critical_segment":
            if stripped.startswith("- "):
                content = stripped[2:]
                cl = content.lower()
                if cl.startswith("name:"):
                    sections["critical_segment"]["name"] = content[5:].strip()
                elif cl.startswith("reason:"):
                    sections["critical_segment"]["reason"] = content[7:].strip()
                elif cl.startswith("delay probability:"):
                    sections["critical_segment"]["delay_probability"] = content[18:].strip()
                elif cl.startswith("hazard type:"):
                    sections["critical_segment"]["hazard_type"] = content[12:].strip()

        elif current_section == "recommendations":
            sections["recommendations"] += stripped + "\n"

        elif current_section == "live_status":
            sections["live_status"] += stripped + "\n"
            if stripped.lower().startswith("- overall route status:"):
                status_text = stripped[23:].strip()
                sl = status_text.lower()
                if "green" in sl or "safe" in sl:
                    sections["overall_status"] = "Green"
                elif "red" in sl or "dangerous" in sl or "high alert" in sl:
                    sections["overall_status"] = "Dangerous"
                else:
                    sections["overall_status"] = "Moderate"
            elif stripped.lower().startswith("- quick decision:"):
                sections["quick_decision"] = stripped[17:].strip()

    # Save final pending segment
    if current_segment and segment_buffer:
        sections["segments"].append(dict(segment_buffer))

    return sections


#  Seeded weather simulation for non-live routes 
def _seeded_checkpoint(node_id: str, index: int, total: int) -> dict:
    """Generate deterministic mock weather for a hub node."""
    h = 0
    for ch in node_id:
        h = ord(ch) + ((h << 5) - h)
    r = abs(h) / 2147483648

    rain  = round(r * 5, 1)
    wind  = round(2 + r * 8, 1)
    temp  = round(24 + r * 10)
    hum   = round(55 + r * 35)
    desc  = "light rain" if rain > 2 else ("partly cloudy" if r > 0.5 else "clear skies")
    sev   = round(min(rain / 10 + wind / 40, 1.0), 3)
    danger = rain > 2.5 or wind > 10

    role = "origin" if index == 0 else ("destination" if index == total - 1 else "mid_route")
    label = node_id.replace("_Hub", "").replace("_DC", "").replace("_", " ")

    return {
        "name":        label,
        "role":        role,
        "is_dangerous": danger,
        "severity":    sev,
        "rain_1h":     rain,
        "wind_speed":  wind,
        "temperature": temp,
        "description": desc,
        "humidity":    hum,
    }


#  Public API 
def get_route_risk_analysis(context: dict) -> dict:
    """
    Generate a full structured route risk analysis.

    context keys:
      - origin (str)
      - destination (str)
      - path_names (list[str])           — full route path from graph engine
      - live_checkpoints (list[dict])    — real OWM data (Pune-Mumbai only)
      - distance_km (float)
      - travel_hrs (float)
      - risk_pct (float)
      - anomaly_score (float)
      - monsoon (bool)
      - perishable (bool)
      - is_disrupted (bool)
    """
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()

    if not REQUESTS_AVAILABLE or not api_key:
        return {
            "available":       False,
            "error":           "AI advisor unavailable — GEMINI_API_KEY not configured.",
            "route_summary":   "",
            "segment_analysis": "",
            "segments":        [],
            "critical_segment": {},
            "recommendations": "",
            "live_status":     "",
            "overall_status":  "Moderate",
            "quick_decision":  "",
            "model":           None,
            "cached":          False,
        }

    origin          = context.get("origin", "Origin")
    destination     = context.get("destination", "Destination")
    path_names      = context.get("path_names", [origin, destination])
    live_checkpoints = context.get("live_checkpoints", [])
    is_pune_mumbai  = (
        "Pune" in origin and "Mumbai" in destination
        or "Mumbai" in origin and "Pune" in destination
    )

    #  Select checkpoint data source 
    if is_pune_mumbai and live_checkpoints:
        checkpoints = live_checkpoints
        data_source = "Live OpenWeatherMap API"
    else:
        # Generate seeded simulation data from path nodes
        checkpoints = [
            _seeded_checkpoint(nid, i, len(path_names))
            for i, nid in enumerate(path_names)
        ]
        data_source = "Simulated (seeded per hub)"

    enriched_context = {
        **context,
        "checkpoints": checkpoints,
        "data_source": data_source,
        "path_names":  path_names,
    }

    fp  = _fingerprint(enriched_context)
    now = time.monotonic()

    #  Cache hit 
    if fp in _cache and (now - _cache[fp]["ts"]) < _CACHE_TTL:
        result = dict(_cache[fp]["result"])
        result["cached"] = True
        return result

    #  Cache miss → call Gemini 
    try:
        prompt = _build_prompt(enriched_context)
        text   = _call_gemini(api_key, prompt)

        parsed = _parse_response(text)

        result = {
            "available":        True,
            "route_summary":    parsed["route_summary"].strip(),
            "segment_analysis": parsed["segment_analysis"].strip(),
            "segments":         parsed["segments"],
            "critical_segment": parsed["critical_segment"],
            "recommendations":  parsed["recommendations"].strip(),
            "live_status":      parsed["live_status"].strip(),
            "overall_status":   parsed["overall_status"],
            "quick_decision":   parsed["quick_decision"],
            "raw_text":         parsed["raw_text"],
            "data_source":      data_source,
            "is_live_weather":  is_pune_mumbai and bool(live_checkpoints),
            "model":            _MODEL_NAME,
            "cached":           False,
        }

        _cache[fp] = {"ts": now, "result": result}
        # Prune stale cache entries
        stale = [k for k, v in _cache.items() if now - v["ts"] >= _CACHE_TTL]
        for k in stale:
            del _cache[k]

        print(f"[InsureRoute] Route risk analysis generated for {origin}→{destination} (key=...{api_key[-6:]})")
        return result

    except Exception as exc:
        logger.error("Route Risk Advisor Gemini error: %s", exc)
        return {
            "available":        False,
            "error":            f"AI advisor temporarily unavailable: {str(exc)[:200]}",
            "route_summary":    "",
            "segment_analysis": "",
            "segments":         [],
            "critical_segment": {},
            "recommendations":  "",
            "live_status":      "",
            "overall_status":   "Moderate",
            "quick_decision":   "",
            "model":            _MODEL_NAME,
            "cached":           False,
        }
