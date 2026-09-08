"""
api.py — FastAPI bridge for the React frontend.

Run:  uvicorn backend.api:app --reload --port 8000
  OR: cd backend && uvicorn api:app --reload --port 8000
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

try:
    try:
        from env_loader import load_insure_route_env
    except ImportError:
        from backend.env_loader import load_insure_route_env
    load_insure_route_env()
except ImportError:
    pass

import asyncio
import logging
import time
from datetime import datetime

from fastapi import APIRouter, Query, BackgroundTasks
from pydantic import BaseModel
from typing import Optional

from legacy.simulation import run_tick, get_summary_stats, _initialize
from legacy.graph_engine import get_node_positions, HUBS, get_graph, find_route

try:
    from legacy.weather_service import fetch_route_weather
    WEATHER_SERVICE_AVAILABLE = True
except ImportError:
    WEATHER_SERVICE_AVAILABLE = False

try:
    from legacy.gemini_advisor import get_ai_advisory
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

try:
    from legacy.news_service import get_route_news
    NEWS_SERVICE_AVAILABLE = True
except ImportError:
    NEWS_SERVICE_AVAILABLE = False

try:
    from legacy.route_risk_advisor import get_route_risk_analysis
    ROUTE_RISK_ADVISOR_AVAILABLE = True
except ImportError:
    ROUTE_RISK_ADVISOR_AVAILABLE = False

try:
    from legacy.route_intelligence_service import get_route_intelligence
    ROUTE_INTELLIGENCE_AVAILABLE = True
except ImportError:
    ROUTE_INTELLIGENCE_AVAILABLE = False

try:
    from legacy.map_directions_service import get_route_geometry, parse_path_query
    MAP_DIRECTIONS_AVAILABLE = True
except ImportError:
    MAP_DIRECTIONS_AVAILABLE = False

logger = logging.getLogger("insure_route.api")

#  App 
legacy_router = APIRouter()

#  Global weather state (updated every 60 s by background task) 
live_weather_state: dict = {
    "is_dangerous": False,
    "reason": "Weather API unavailable - running on ML detection only",
    "checkpoints": [],
    "api_status": "initialising",
    "last_checked": None,
}

_weather_task_running = False


#  Background weather polling loop 
async def _weather_polling_loop():
    """Poll OpenWeatherMap every 60 seconds and update live_weather_state."""
    global live_weather_state, _weather_task_running
    _weather_task_running = True
    while True:
        try:
            if WEATHER_SERVICE_AVAILABLE:
                # Run blocking I/O in thread pool so we don't block the event loop
                result = await asyncio.get_event_loop().run_in_executor(
                    None, fetch_route_weather
                )
                live_weather_state = result

                if result.get("is_dangerous"):
                    point  = result.get("disruption_point", "unknown")
                    reason = result.get("reason", "")
                    print(
                        f"[InsureRoute] LIVE WEATHER AUTO-TRIGGERED "
                        f"at {point}: {reason}"
                    )
                    logger.warning(
                        "LIVE WEATHER AUTO-TRIGGERED at %s: %s", point, reason
                    )
            else:
                live_weather_state = {
                    "is_dangerous": False,
                    "reason": "Weather service module not available",
                    "checkpoints": [],
                    "api_status": "offline",
                    "last_checked": datetime.utcnow().isoformat(),
                }
        except Exception as exc:
            logger.error("Weather polling error: %s", exc)
            live_weather_state = {
                "is_dangerous": False,
                "reason": "Weather API unavailable - running on ML detection only",
                "checkpoints": [],
                "api_status": "offline",
                "last_checked": datetime.utcnow().isoformat(),
            }
        await asyncio.sleep(60)


#  Startup: warm ML engine + kick off weather polling 
@legacy_router.on_event("startup")
async def startup():
    # Keep startup non-blocking so the service can bind PORT quickly.
    asyncio.create_task(asyncio.to_thread(_initialize))
    # Fire the first weather check immediately (non-blocking)
    asyncio.create_task(_weather_polling_loop())


#  Schemas 
class DisruptionRequest(BaseModel):
    origin: str = "Pune_Hub"
    destination: str = "Mumbai_Hub"
    cargo_type: str = "Standard"
    monsoon: bool = True
    anomaly_threshold: float = -0.15


#  Helpers 
def build_graph_payload():
    G = get_graph()
    positions = get_node_positions()
    nodes = []
    for hub in HUBS:
        pos = positions.get(hub, (80.0, 20.0))
        nodes.append({"id": hub, "label": hub.replace("_", " "), "lon": pos[0], "lat": pos[1]})

    edges = []
    for src, dst, data in list(G.edges(data=True))[:200]:
        edges.append({
            "source": src,
            "target": dst,
            "weight": data.get("weight", 1),
            "distance": data.get("distance", 0),
        })
    return nodes, edges


#  Routes 
@legacy_router.get("/health")
def health():
    return {"status": "ok", "ts": time.time()}


@legacy_router.get("/hubs")
def hubs():
    return {"hubs": HUBS}


@legacy_router.get("/map-directions")
def map_directions(
    path: str = Query(
        "[]",
        description='JSON array of hub ids in strict order, e.g. ["Delhi_Hub","Jaipur_Hub"]',
    ),
):
    """
    Road-following route geometry (OpenRouteService) for map polylines.
    Falls back to ordered hub coordinates when API key is missing or ORS errors.
    """
    if not MAP_DIRECTIONS_AVAILABLE:
        return {
            "mode": "fallback",
            "coordinates": [],
            "message": " Optimized route unavailable (service module missing)",
        }
    ids = parse_path_query(path)
    if len(ids) < 2:
        return {
            "mode": "fallback",
            "coordinates": [],
            "message": " Optimized route unavailable (need at least 2 waypoints)",
        }
    positions = get_node_positions()
    return get_route_geometry(ids, positions)


@legacy_router.get("/weather-status")
def weather_status(origin: str = Query(None), destination: str = Query(None)):
    """Returns the latest live weather assessment for the route checkpoints."""
    if origin and destination and WEATHER_SERVICE_AVAILABLE:
        path_nodes = find_route(origin, destination).get("path", [origin, destination])
        return fetch_route_weather(path_nodes)
    return live_weather_state


@legacy_router.get("/data")
def get_data(
    origin: str = Query("Pune_Hub"),
    destination: str = Query("Mumbai_Hub"),
    cargo_type: str = Query("Standard"),
    monsoon: bool = Query(True),
    anomaly_threshold: float = Query(-0.15),
):
    path_nodes = find_route(origin, destination).get("path", [origin, destination])
    if WEATHER_SERVICE_AVAILABLE:
        weather = fetch_route_weather(path_nodes)
    else:
        import copy
        weather = copy.deepcopy(live_weather_state)

    #  Decide whether live weather forces a disruption 
    weather_triggered = weather.get("is_dangerous", False)
    weather_severity  = weather.get("severity", 0.0) if weather_triggered else 0.0

    # Cargo-specific risk modifications
    for cp in weather.get("checkpoints", []):
        if cargo_type == "Electronics" and (cp.get("humidity", 0) > 75 or cp.get("rain_1h", 0) > 1.0):
            weather_triggered = True
            weather_severity = max(weather_severity, 0.45)
            weather["reason"] = f"High humidity/rain detected at {cp['name']}, risking Electronics cargo."
            weather["is_dangerous"] = True
            break
        elif cargo_type in ["Pharmaceuticals", "Perishable Goods"] and cp.get("temperature", 25) > 30:
            weather_triggered = True
            weather_severity = max(weather_severity, 0.4)
            weather["reason"] = f"Dangerous temperature ({cp.get('temperature')}°C) at {cp['name']}, risking {cargo_type}."
            weather["is_dangerous"] = True
            break
        elif cargo_type == "Heavy Machinery" and cp.get("wind_speed", 0) > 8:
            weather_triggered = True
            weather_severity = max(weather_severity, 0.38)
            weather["reason"] = f"Strong winds at {cp['name']}, risky for Heavy Machinery transport."
            weather["is_dangerous"] = True
            break
        elif cargo_type == "Textiles" and cp.get("humidity", 0) > 80:
            weather_triggered = True
            weather_severity = max(weather_severity, 0.35)
            weather["reason"] = f"High humidity ({cp.get('humidity')}%) at {cp['name']}, moisture absorption risk for Textiles."
            weather["is_dangerous"] = True
            break
        elif cargo_type == "Chemicals" and cp.get("temperature", 25) > 35:
            weather_triggered = True
            weather_severity = max(weather_severity, 0.50)
            weather["reason"] = f"Extreme temperature ({cp.get('temperature')}°C) at {cp['name']}, reaction risk for Chemicals."
            weather["is_dangerous"] = True
            break
        elif cargo_type == "Automotive Parts" and (cp.get("humidity", 0) > 70 and cp.get("rain_1h", 0) > 0.5):
            weather_triggered = True
            weather_severity = max(weather_severity, 0.32)
            weather["reason"] = f"Rain + humidity at {cp['name']}, corrosion risk for Automotive Parts."
            weather["is_dangerous"] = True
            break

    tick = run_tick(
        origin=origin,
        destination=destination,
        cargo_value=1000000,
        monsoon=monsoon,
        perishable=(cargo_type in ["Pharmaceuticals", "Perishable Goods"]),
        inject_disruption=weather_triggered,
        anomaly_threshold=anomaly_threshold,
        cargo_type=cargo_type,
    )
    stats = get_summary_stats()
    nodes, edges = build_graph_payload()

    #  Override / augment pricing when driven by live weather 
    pricing = tick["pricing"]
    if weather_triggered:
        weather_multiplier = round(min(weather_severity * 1.4, 1.8), 3)
        # Patch the pricing dict in-place (all formula logic untouched)
        pricing["weather_multiplier"] = weather_multiplier

    response = {
        "kpis": {
            "sla":               stats["sla_breach_rate"],
            "delay":             stats["avg_delay_pct"],
            "risk":              round(tick["disruption_probability"] * 100, 1),
            "savings":           pricing["savings_pct"],
            "total_disruptions": stats["total_disruptions"],
            "total_shipments":   stats["total_shipments"],
        },
        "insurance": {
            "cargo_value":            pricing["cargo_value"],
            "disruption_probability": tick["disruption_probability"],
            "base_premium":           pricing["base_premium"],
            "before_cost":            pricing["hedge_cost_before"],
            "after_cost":             pricing["hedge_cost_after"],
            "savings":                pricing["savings_inr"],
            "savings_pct":            pricing["savings_pct"],
            "weather_multiplier":     pricing["weather_multiplier"],
            "perishable_multiplier":  pricing["perishable_multiplier"],
            "cargo_multiplier":       pricing.get("cargo_multiplier", 1.0),
            "temp_multiplier":        pricing.get("temp_multiplier", 1.0),
            "fragility_multiplier":   pricing.get("fragility_multiplier", 1.0),
            "value_density_multiplier": pricing.get("value_density_multiplier", 1.0),
            "cargo_type":             pricing.get("cargo_type", cargo_type),
            "cargo_profile":          pricing.get("cargo_profile", {}),
        },
        "route": {
            **tick["route"],
            "disruption_detected": tick["disruption_detected"] or weather_triggered,
            "origin":      tick["origin"],
            "destination": tick["destination"],
        },
        "anomaly_score": tick["anomaly_score"],
        "nodes": nodes,
        "edges": edges,
        "flags": tick["flags"],
        "raw":   tick["raw_sample"],
        #  Weather metadata 
        "trigger_source":  "LIVE_WEATHER"   if weather_triggered else "MANUAL_OR_ML",
        "live_data":       True,
        **(
            {
                "weather_alert":     weather.get("reason"),
                "disruption_point":  weather.get("disruption_point"),
                "alternate_via":     weather.get("alternate_route_via") or "Alternative Corridor",
                "cargo_type":        cargo_type,
                "weather_clear":     False,
            }
            if weather_triggered
            else {"weather_clear": True}
        ),
    }
    return response


@legacy_router.post("/inject-disruption")
def inject_disruption(req: DisruptionRequest):
    #  Unchanged — manual injection path 
    tick = run_tick(
        origin=req.origin,
        destination=req.destination,
        cargo_value=1000000,
        monsoon=req.monsoon,
        perishable=req.cargo_type in ["Pharmaceuticals", "Perishable Goods"],
        inject_disruption=True,
        anomaly_threshold=req.anomaly_threshold,
        cargo_type=req.cargo_type,
    )
    stats = get_summary_stats()
    nodes, edges = build_graph_payload()

    return {
        "kpis": {
            "sla":               stats["sla_breach_rate"],
            "delay":             stats["avg_delay_pct"],
            "risk":              round(tick["disruption_probability"] * 100, 1),
            "savings":           tick["pricing"]["savings_pct"],
            "total_disruptions": stats["total_disruptions"],
            "total_shipments":   stats["total_shipments"],
        },
        "insurance": {
            "cargo_value":            tick["pricing"]["cargo_value"],
            "disruption_probability": tick["disruption_probability"],
            "base_premium":           tick["pricing"]["base_premium"],
            "before_cost":            tick["pricing"]["hedge_cost_before"],
            "after_cost":             tick["pricing"]["hedge_cost_after"],
            "savings":                tick["pricing"]["savings_inr"],
            "savings_pct":            tick["pricing"]["savings_pct"],
            "weather_multiplier":     tick["pricing"]["weather_multiplier"],
            "perishable_multiplier":  tick["pricing"]["perishable_multiplier"],
            "cargo_multiplier":       tick["pricing"].get("cargo_multiplier", 1.0),
            "temp_multiplier":        tick["pricing"].get("temp_multiplier", 1.0),
            "fragility_multiplier":   tick["pricing"].get("fragility_multiplier", 1.0),
            "value_density_multiplier": tick["pricing"].get("value_density_multiplier", 1.0),
            "cargo_type":             tick["pricing"].get("cargo_type", req.cargo_type),
            "cargo_profile":          tick["pricing"].get("cargo_profile", {}),
        },
        "route": {
            **tick["route"],
            "disruption_detected": tick["disruption_detected"],
            "origin":      tick["origin"],
            "destination": tick["destination"],
        },
        "anomaly_score": tick["anomaly_score"],
        "nodes":   nodes,
        "edges":   edges,
        "flags":   tick["flags"],
        "raw":     tick["raw_sample"],
        "injected": True,
        "trigger_source": "MANUAL_OR_ML",
        "live_data": True,
    }


@legacy_router.get("/ai-advisor")
def ai_advisor(
    origin: str = Query("Pune_Hub"),
    destination: str = Query("Mumbai_Hub"),
    cargo_value: float = Query(70000),
    monsoon: bool = Query(True),
    perishable: bool = Query(True),
    anomaly_threshold: float = Query(-0.15),
):
    """Generate an AI risk assessment using Google Gemini."""
    if not GEMINI_AVAILABLE:
        return {
            "available": False,
            "summary": "Gemini advisor module not installed.",
            "actions": [],
            "insurance_tip": "",
            "model": None,
        }

    if WEATHER_SERVICE_AVAILABLE:
        path_nodes = find_route(origin, destination).get("path", [origin, destination])
        weather = fetch_route_weather(path_nodes)
    else:
        weather = live_weather_state
    weather_triggered = weather.get("is_dangerous", False)

    tick = run_tick(
        origin=origin,
        destination=destination,
        cargo_value=cargo_value,
        monsoon=monsoon,
        perishable=perishable,
        inject_disruption=weather_triggered,
        anomaly_threshold=anomaly_threshold,
    )
    stats = get_summary_stats()

    context = {
        "kpis": {
            "sla": stats["sla_breach_rate"],
            "delay": stats["avg_delay_pct"],
            "risk": round(tick["disruption_probability"] * 100, 1),
            "savings": tick["pricing"]["savings_pct"],
        },
        "insurance": {
            "cargo_value": tick["pricing"]["cargo_value"],
            "disruption_probability": tick["disruption_probability"],
            "base_premium": tick["pricing"]["base_premium"],
            "before_cost": tick["pricing"]["hedge_cost_before"],
            "after_cost": tick["pricing"]["hedge_cost_after"],
            "savings": tick["pricing"]["savings_inr"],
            "savings_pct": tick["pricing"]["savings_pct"],
            "weather_multiplier": tick["pricing"]["weather_multiplier"],
            "perishable_multiplier": tick["pricing"]["perishable_multiplier"],
        },
        "route": {
            **tick["route"],
            "disruption_detected": tick["disruption_detected"] or weather_triggered,
            "origin": tick["origin"],
            "destination": tick["destination"],
        },
        "anomaly_score": tick["anomaly_score"],
        "flags": tick["flags"],
        "trigger_source": "LIVE_WEATHER" if weather_triggered else "MANUAL_OR_ML",
        "weather": weather if weather_triggered else {},
    }
    return get_ai_advisory(context)


@legacy_router.get("/route-news")
def route_news(
    origin:      str   = Query("Pune_Hub"),
    destination: str   = Query("Mumbai_Hub"),
    cargo_value: float = Query(70000),
    monsoon:     bool  = Query(True),
    perishable:  bool  = Query(True),
    anomaly_threshold: float = Query(-0.15),
):
    """Generate a route-specific AI intelligence brief using Gemini."""
    if not NEWS_SERVICE_AVAILABLE:
        return {
            "available": False,
            "briefs": ["News service module not installed."],
            "cached": False,
            "route": f"{origin} → {destination}",
        }

    if WEATHER_SERVICE_AVAILABLE:
        path_nodes = find_route(origin, destination).get("path", [origin, destination])
        weather = fetch_route_weather(path_nodes)
    else:
        weather = live_weather_state
    weather_triggered = weather.get("is_dangerous", False)

    # Run a quick tick to get the risk score for this specific route
    tick = run_tick(
        origin=origin,
        destination=destination,
        cargo_value=cargo_value,
        monsoon=monsoon,
        perishable=perishable,
        inject_disruption=weather_triggered,
        anomaly_threshold=anomaly_threshold,
    )

    route_info  = tick.get("route", {})
    path_names  = route_info.get("path", [origin, destination])
    distance_km = route_info.get("total_distance_km", (len(path_names) - 1) * 150)
    travel_hrs  = route_info.get("total_time_hrs", round(distance_km / 60, 1))

    context = {
        "origin":           origin,
        "destination":      destination,
        "path_names":       path_names,
        "live_checkpoints": weather.get("checkpoints", []),
        "distance_km":      distance_km,
        "travel_hrs":       travel_hrs,
        "risk_pct":         round(tick["disruption_probability"] * 100, 1),
        "anomaly_score":    tick["anomaly_score"],
        "monsoon":          monsoon,
        "perishable":       perishable,
        "is_disrupted":     tick["disruption_detected"] or weather_triggered,
    }

    return get_route_news(context)


@legacy_router.get("/route-intelligence")
def route_intelligence(
    origin: str = Query("Pune_Hub"),
    destination: str = Query("Mumbai_Hub"),
):
    """Return route risk, weather, traffic and route-filtered live news."""
    if not ROUTE_INTELLIGENCE_AVAILABLE:
        return {
            "available": False,
            "route": {
                "origin": origin,
                "destination": destination,
                "path_nodes": [origin, destination],
                "coordinates": [],
                "waypoints": [],
                "bounding_box": {},
                "distance_km": 0,
                "travel_time_hrs": 0,
            },
            "risks": [],
            "weather": [],
            "traffic": [],
            "news": [],
            "risk_score": 0,
            "intelligence_highlight": "Route intelligence module unavailable.",
            "news_status": {
                "mode": "fallback_demo",
                "message": "Live news unavailable (service module missing)",
            },
        }

    return get_route_intelligence(origin=origin, destination=destination)


@legacy_router.get("/route-risk-analysis")
def route_risk_analysis(
    origin:      str   = Query("Pune_Hub"),
    destination: str   = Query("Mumbai_Hub"),
    path:        str   = Query(""),        # JSON-encoded list of node IDs
    cargo_value: float = Query(70000),
    monsoon:     bool  = Query(True),
    perishable:  bool  = Query(True),
    anomaly_threshold: float = Query(-0.15),
):
    """
    Generate a full structured route risk analysis for ANY source→destination.
    - For Pune-Mumbai: injects live OWM weather checkpoint data.
    - For all other routes: uses path node IDs with seeded simulation weather.
    """
    if not ROUTE_RISK_ADVISOR_AVAILABLE:
        return {
            "available": False,
            "error": "Route risk advisor module not installed.",
            "overall_status": "Moderate",
        }

    # Parse path from JSON query param
    try:
        import json as _json
        path_names = _json.loads(path) if path else [origin, destination]
    except Exception:
        path_names = [origin, destination]

    # Run a tick to get ML model output
    if WEATHER_SERVICE_AVAILABLE:
        weather = fetch_route_weather(path_names)
    else:
        weather = live_weather_state
    weather_triggered = weather.get("is_dangerous", False)

    tick = run_tick(
        origin=origin,
        destination=destination,
        cargo_value=cargo_value,
        monsoon=monsoon,
        perishable=perishable,
        inject_disruption=weather_triggered,
        anomaly_threshold=anomaly_threshold,
    )

    route_info = tick.get("route", {})
    distance_km = route_info.get("total_distance_km", (len(path_names) - 1) * 150)
    travel_hrs  = route_info.get("total_time_hrs",    round(distance_km / 60, 1))

    # If path not provided, use the ML engine's computed path
    if not path_names or path_names == [origin, destination]:
        engine_path = route_info.get("path", [origin, destination])
        if engine_path and len(engine_path) >= 2:
            path_names = engine_path

    context = {
        "origin":           origin,
        "destination":      destination,
        "path_names":       path_names,
        "live_checkpoints": weather.get("checkpoints", []),
        "distance_km":      distance_km,
        "travel_hrs":       travel_hrs,
        "risk_pct":         round(tick["disruption_probability"] * 100, 1),
        "anomaly_score":    tick["anomaly_score"],
        "monsoon":          monsoon,
        "perishable":       perishable,
        "is_disrupted":     tick["disruption_detected"] or weather_triggered,
    }

    return get_route_risk_analysis(context)

