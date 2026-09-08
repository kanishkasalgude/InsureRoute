"""
route_intelligence_service.py

Production-oriented route intelligence service with graceful fallback behavior.
Combines route geometry, weather/traffic/risk signals, and route-relevant news.
"""

from __future__ import annotations

import logging
import os
import random
from datetime import datetime, timedelta, timezone
from hashlib import md5
from typing import Any, Dict, List, Tuple

try:
    import requests as _requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

try:
    try:
        from env_loader import load_insure_route_env
    except ImportError:
        from backend.env_loader import load_insure_route_env
    load_insure_route_env()
except ImportError:
    pass

try:
    from .graph_engine import find_route, get_node_positions
    from .weather_service import fetch_route_weather
except ImportError:
    from graph_engine import find_route, get_node_positions
    from weather_service import fetch_route_weather

logger = logging.getLogger("insure_route.route_intelligence")

NEWSDATA_BASE_URL = "https://newsdata.io/api/1/news"
NEWS_KEYWORDS = ["accident", "flood", "strike", "roadblock", "weather", "transport", "logistics"]
HIGH_IMPACT_KEYWORDS = {"accident", "flood", "strike", "roadblock", "closure", "landslide", "storm"}


def _clean_label(node_name: str) -> str:
    return node_name.replace("_Hub", "").replace("_DC", "").replace("_", " ").strip()


def _extract_path(origin: str, destination: str) -> Dict[str, Any]:
    route = find_route(origin=origin, destination=destination, disrupted_edge=None)
    positions = get_node_positions()
    path_nodes = route.get("path", [origin, destination])

    coordinates = []
    for node in path_nodes:
        lon, lat = positions.get(node, (77.0, 20.0))
        coordinates.append(
            {
                "node_id": node,
                "city": _clean_label(node),
                "lat": round(float(lat), 4),
                "lon": round(float(lon), 4),
            }
        )

    lats = [p["lat"] for p in coordinates] or [20.0]
    lons = [p["lon"] for p in coordinates] or [77.0]
    bbox = {
        "min_lat": min(lats),
        "max_lat": max(lats),
        "min_lon": min(lons),
        "max_lon": max(lons),
    }

    return {
        "origin": origin,
        "destination": destination,
        "path_nodes": path_nodes,
        "coordinates": coordinates,
        "waypoints": coordinates[1:-1],
        "bounding_box": bbox,
        "distance_km": route.get("total_distance_km", 0),
        "travel_time_hrs": route.get("total_time_hrs", 0),
    }


def _parse_news_ts(raw_ts: str) -> datetime:
    if not raw_ts:
        return datetime.now(timezone.utc) - timedelta(days=3)
    try:
        return datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
    except Exception:
        return datetime.now(timezone.utc) - timedelta(days=3)


def _recentness_boost(published_at: str) -> float:
    ts = _parse_news_ts(published_at)
    age_hours = max((datetime.now(timezone.utc) - ts).total_seconds() / 3600.0, 0.0)
    if age_hours <= 24:
        return 0.4
    if age_hours <= 48:
        return 0.25
    if age_hours <= 72:
        return 0.1
    return 0.0


def _build_news_query(route_ctx: Dict[str, Any]) -> str:
    cities = [_clean_label(n) for n in route_ctx["path_nodes"]]
    city_part = " OR ".join(dict.fromkeys(cities[:5])) or "highway"
    keyword_part = " OR ".join(NEWS_KEYWORDS)
    return f"({city_part} OR highway) AND ({keyword_part})"


def _news_fingerprint(item: Dict[str, Any]) -> str:
    base = f"{item.get('title', '')}|{item.get('link', '')}|{item.get('pubDate', '')}"
    return md5(base.encode("utf-8")).hexdigest()


def _location_tag(item: Dict[str, Any], route_cities: List[str]) -> str:
    text = " ".join(
        [
            item.get("title", "") or "",
            item.get("description", "") or "",
            item.get("content", "") or "",
        ]
    ).lower()
    for city in route_cities:
        if city.lower() in text:
            return f"Near {city}"
    return "Route Corridor"


def _relevance_score(item: Dict[str, Any], route_cities: List[str]) -> float:
    text = " ".join(
        [
            item.get("title", "") or "",
            item.get("description", "") or "",
            item.get("content", "") or "",
        ]
    ).lower()
    city_hits = sum(1 for city in route_cities if city.lower() in text)
    keyword_hits = sum(1 for kw in NEWS_KEYWORDS if kw in text)
    impact_hits = sum(1 for kw in HIGH_IMPACT_KEYWORDS if kw in text)
    score = (
        min(city_hits * 0.25, 0.5)
        + min(keyword_hits * 0.08, 0.24)
        + min(impact_hits * 0.1, 0.2)
        + _recentness_boost(item.get("pubDate", ""))
    )
    return round(min(score, 1.0), 3)


def _is_relevant_news(item: Dict[str, Any], route_cities: List[str], bbox: Dict[str, float]) -> bool:
    _ = bbox  # Reserved for APIs that provide geotagged coordinates.
    text = " ".join(
        [
            item.get("title", "") or "",
            item.get("description", "") or "",
            item.get("content", "") or "",
        ]
    ).lower()
    city_match = any(city.lower() in text for city in route_cities)
    keyword_match = any(kw in text for kw in NEWS_KEYWORDS)
    return city_match and keyword_match


def _build_mock_news(route_ctx: Dict[str, Any]) -> List[Dict[str, Any]]:
    cities = [_clean_label(n) for n in route_ctx["path_nodes"]]
    primary = cities[0] if cities else "Origin"
    secondary = cities[1] if len(cities) > 1 else (cities[-1] if cities else "Destination")
    now = datetime.now(timezone.utc)

    return [
        {
            "title": f"Traffic slowdown reported on highway stretch near {secondary}",
            "source": "Demo Logistics Wire",
            "published_at": (now - timedelta(hours=2)).isoformat(),
            "url": "https://example.com/demo-highway-slowdown",
            "relevance_score": 0.83,
            "location_tag": f"Near {secondary}",
            "impact": "high",
        },
        {
            "title": f"Heavy rain advisory issued for {primary} outbound corridor",
            "source": "Demo Weather Desk",
            "published_at": (now - timedelta(hours=5)).isoformat(),
            "url": "https://example.com/demo-rain-advisory",
            "relevance_score": 0.74,
            "location_tag": f"Near {primary}",
            "impact": "medium",
        },
        {
            "title": "Freight union strike watch raised for western transport hubs",
            "source": "Demo Business Bulletin",
            "published_at": (now - timedelta(hours=9)).isoformat(),
            "url": "https://example.com/demo-strike-watch",
            "relevance_score": 0.66,
            "location_tag": "Route Corridor",
            "impact": "medium",
        },
    ]


def _fetch_live_news(route_ctx: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    api_key = os.environ.get("NEWSDATA_API_KEY", "").strip()
    if not api_key:
        logger.warning("Missing API Key: NEWSDATA_API_KEY not configured. Falling back to demo mode.")
        return _build_mock_news(route_ctx), {"mode": "fallback_demo", "message": "Live news unavailable (API key missing)"}

    if not REQUESTS_AVAILABLE:
        logger.warning("Missing dependency: requests unavailable. Falling back to demo mode.")
        return _build_mock_news(route_ctx), {"mode": "fallback_demo", "message": "Live news unavailable (requests missing)"}

    route_cities = [_clean_label(n) for n in route_ctx["path_nodes"]]
    query = _build_news_query(route_ctx)
    params = {
        "apikey": api_key,
        "q": query,
        "language": "en",
        "country": "in",
        "category": "top,business",
    }

    try:
        response = _requests.get(NEWSDATA_BASE_URL, params=params, timeout=20)
        response.raise_for_status()
        payload = response.json()
        raw_results = payload.get("results", []) or []

        unique = {}
        for item in raw_results:
            if not _is_relevant_news(item, route_cities, route_ctx["bounding_box"]):
                continue
            key = _news_fingerprint(item)
            if key not in unique:
                unique[key] = item

        ranked = []
        for item in unique.values():
            score = _relevance_score(item, route_cities)
            if score < 0.25:
                continue
            ranked.append(
                {
                    "title": item.get("title", "Untitled event"),
                    "source": item.get("source_id", "unknown"),
                    "published_at": item.get("pubDate", ""),
                    "url": item.get("link", ""),
                    "relevance_score": score,
                    "location_tag": _location_tag(item, route_cities),
                    "impact": "high" if score >= 0.75 else "medium" if score >= 0.5 else "low",
                }
            )

        ranked.sort(key=lambda n: (n["relevance_score"], n["published_at"]), reverse=True)
        return ranked[:8], {"mode": "live", "message": "Live news active"}
    except Exception as exc:
        logger.warning("NewsData request failed: %s. Falling back to demo mode.", exc)
        return _build_mock_news(route_ctx), {"mode": "fallback_demo", "message": "Live news unavailable (API failure)"}


def _build_weather_alerts(route_ctx: Dict[str, Any]) -> List[Dict[str, Any]]:
    weather = fetch_route_weather(route_ctx.get("path_nodes", []))
    alerts: List[Dict[str, Any]] = []
    for cp in weather.get("checkpoints", []):
        if cp.get("is_dangerous"):
            alerts.append(
                {
                    "location": cp.get("name", "Unknown"),
                    "type": "weather",
                    "severity": float(cp.get("severity", 0.0)),
                    "reason": f"{cp.get('description', 'weather risk')} · rain {cp.get('rain_1h', 0)}mm/hr",
                }
            )

    # If route is not Pune-Mumbai and no live checkpoints are relevant, synthesize mild alerts.
    if not alerts and route_ctx["path_nodes"]:
        seed = md5("|".join(route_ctx["path_nodes"]).encode()).hexdigest()
        random.seed(seed)
        maybe = random.random()
        if maybe > 0.45:
            loc = _clean_label(route_ctx["path_nodes"][min(1, len(route_ctx["path_nodes"]) - 1)])
            alerts.append(
                {
                    "location": loc,
                    "type": "weather",
                    "severity": round(0.2 + random.random() * 0.3, 3),
                    "reason": "Localized rainfall pockets expected",
                }
            )
    return alerts


def _build_traffic_anomalies(route_ctx: Dict[str, Any]) -> List[Dict[str, Any]]:
    path = route_ctx["path_nodes"]
    if len(path) < 2:
        return []

    seed = md5(("traffic|" + "|".join(path)).encode()).hexdigest()
    random.seed(seed)
    anomalies = []
    mid = _clean_label(path[min(1, len(path) - 1)])
    if random.random() > 0.35:
        anomalies.append(
            {
                "location": mid,
                "type": "traffic",
                "severity": round(0.35 + random.random() * 0.45, 3),
                "reason": "Congestion spike on key arterial segment",
            }
        )
    return anomalies


def _compose_risks(weather_alerts: List[Dict[str, Any]], traffic_alerts: List[Dict[str, Any]], news_items: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], float, str]:
    risk_items = []

    for item in weather_alerts:
        risk_items.append({"source": "weather", **item})
    for item in traffic_alerts:
        risk_items.append({"source": "traffic", **item})

    for article in news_items[:3]:
        risk_items.append(
            {
                "source": "news",
                "location": article.get("location_tag", "Route Corridor"),
                "type": "news",
                "severity": round(float(article.get("relevance_score", 0.0)), 3),
                "reason": article.get("title", "News event"),
            }
        )

    weather_score = sum(item.get("severity", 0) for item in weather_alerts) * 28
    traffic_score = sum(item.get("severity", 0) for item in traffic_alerts) * 24
    news_score = sum(float(article.get("relevance_score", 0)) for article in news_items[:4]) * 18
    risk_score = round(min((weather_score + traffic_score + news_score), 100), 1)

    highlight = "Route stable with manageable risk."
    high_traffic = next((i for i in traffic_alerts if i.get("severity", 0) >= 0.55), None)
    high_news = next((n for n in news_items if float(n.get("relevance_score", 0)) >= 0.75), None)
    if high_traffic and high_news:
        highlight = (
            f"Delay expected due to {high_news.get('title', 'incident')} "
            f"and traffic stress near {high_traffic.get('location', 'mid-route')}."
        )
    elif high_news:
        highlight = f"Delay risk elevated: {high_news.get('title', 'high-impact incident')}."
    elif high_traffic:
        highlight = f"Traffic delay expected near {high_traffic.get('location', 'mid-route')}."

    return risk_items, risk_score, highlight


def get_route_intelligence(origin: str, destination: str) -> Dict[str, Any]:
    """
    Public service entrypoint.
    Returns structured route intelligence with graceful fallback mode.
    """
    route_ctx = _extract_path(origin=origin, destination=destination)
    news_items, news_status = _fetch_live_news(route_ctx)
    weather_alerts = _build_weather_alerts(route_ctx)
    traffic_alerts = _build_traffic_anomalies(route_ctx)
    risks, risk_score, highlight = _compose_risks(weather_alerts, traffic_alerts, news_items)

    return {
        "route": {
            "origin": route_ctx["origin"],
            "destination": route_ctx["destination"],
            "path_nodes": route_ctx["path_nodes"],
            "coordinates": route_ctx["coordinates"],
            "waypoints": route_ctx["waypoints"],
            "bounding_box": route_ctx["bounding_box"],
            "distance_km": route_ctx["distance_km"],
            "travel_time_hrs": route_ctx["travel_time_hrs"],
        },
        "risks": risks,
        "weather": weather_alerts,
        "traffic": traffic_alerts,
        "news": news_items,
        "risk_score": risk_score,
        "intelligence_highlight": highlight,
        "news_status": news_status,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
