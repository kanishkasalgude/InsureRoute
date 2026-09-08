"""
Road geometry for route visualization via OpenRouteService (ORS).

If OPENROUTESERVICE_API_KEY is missing or ORS fails, returns the same
waypoint coordinates in order so the client can draw a dashed fallback polyline.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Tuple

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

logger = logging.getLogger("insure_route.map_directions")

ORS_URL = "https://api.openrouteservice.org/v2/directions/driving-car/geojson"
_MAX_POINTS = 1800


def _decimate(coords: List[List[float]], max_pts: int = _MAX_POINTS) -> List[List[float]]:
    if len(coords) <= max_pts:
        return coords
    step = max(1, len(coords) // max_pts)
    return coords[::step]


def _hub_coordinates_in_order(path_ids: List[str], positions: Dict[str, Tuple[float, float]]) -> List[List[float]]:
    """Strict hub order → [[lon, lat], ...] for ORS / fallback."""
    out: List[List[float]] = []
    for hid in path_ids:
        pos = positions.get(hid)
        if pos is None:
            logger.warning("Unknown hub id in route path (no coordinates): %s", hid)
            continue
        lon, lat = float(pos[0]), float(pos[1])
        out.append([lon, lat])
    return out


def _ors_post(body: Dict[str, Any], api_key: str) -> Dict[str, Any]:
    resp = requests.post(
        ORS_URL,
        json=body,
        headers={"Authorization": api_key, "Content-Type": "application/json"},
        timeout=40,
    )
    resp.raise_for_status()
    return resp.json()


def _feature_to_variant(feat: Dict[str, Any]) -> Dict[str, Any]:
    geometry = (feat.get("geometry") or {})
    line = geometry.get("coordinates") or []
    line = _decimate([[float(c[0]), float(c[1])] for c in line])
    props = feat.get("properties") or {}
    summ = props.get("summary") or {}
    duration = float(summ.get("duration", 0) or 0)
    distance = float(summ.get("distance", 0) or 0)
    if (duration <= 0 or distance <= 0) and props.get("segments"):
        segs = props.get("segments") or []
        duration = sum(float(s.get("duration", 0) or 0) for s in segs)
        distance = sum(float(s.get("distance", 0) or 0) for s in segs)
    return {
        "coordinates": line,
        "duration_sec": duration,
        "distance_m": distance,
    }


def get_route_geometry(path_ids: List[str], positions: Dict[str, Tuple[float, float]]) -> Dict[str, Any]:
    """
    Returns:
      mode: "road" | "fallback"
      coordinates: [[lon, lat], ...] — best / first variant (backward compatible)
      variants: [{ id, label, coordinates, duration_sec, distance_m, is_best }, ...]
      message: optional UI / dev hint
    """
    coords = _hub_coordinates_in_order(path_ids, positions)
    if len(coords) < 2:
        return {
            "mode": "fallback",
            "coordinates": coords,
            "variants": [],
            "message": "Not enough waypoints to build a route line.",
        }

    api_key = os.environ.get("OPENROUTESERVICE_API_KEY", "").strip()
    if not api_key or not REQUESTS_AVAILABLE:
        logger.warning(
            "OpenRouteService unavailable (missing OPENROUTESERVICE_API_KEY or requests). "
            "Using waypoint fallback polyline."
        )
        return {
            "mode": "fallback",
            "coordinates": coords,
            "variants": [],
            "message": "WARNING: Optimized route unavailable (API missing)",
        }

    base_body: Dict[str, Any] = {"coordinates": coords}

    def _fallback_response(msg: str) -> Dict[str, Any]:
        return {
            "mode": "fallback",
            "coordinates": coords,
            "variants": [],
            "message": msg,
        }

    try:
        # Try with alternative routes (Google-Maps-style options) when possible
        data: Dict[str, Any] = {}
        try:
            data = _ors_post(
                {
                    **base_body,
                    "alternative_routes": {
                        "target_count": 2,
                        "share_factor": 0.65,
                        "weight_factor": 1.32,
                    },
                },
                api_key,
            )
        except Exception:
            data = _ors_post(base_body, api_key)

        features = data.get("features") or []
        if not features:
            raise ValueError("empty GeoJSON features")

        # Rank by driving duration; first = recommended default
        ranked = sorted(
            enumerate(features),
            key=lambda it: float(((it[1].get("properties") or {}).get("summary") or {}).get("duration", 1e18) or 1e18),
        )

        variants: List[Dict[str, Any]] = []
        for rank, (_, feat) in enumerate(ranked):
            v = _feature_to_variant(feat)
            v["id"] = "best" if rank == 0 else f"alt_{rank}"
            v["is_best"] = rank == 0
            v["label"] = "Best route (fastest)" if rank == 0 else f"Alternative {rank}"
            variants.append(v)

        best_line = variants[0]["coordinates"] if variants else []
        if len(best_line) < 2:
            raise ValueError("invalid line geometry")

        return {
            "mode": "road",
            "coordinates": best_line,
            "variants": variants,
            "message": None,
        }
    except Exception as exc:
        logger.warning("ORS directions failed: %s — using waypoint fallback.", exc)
        return _fallback_response("WARNING: Optimized route unavailable (routing API failure)")


def parse_path_query(path: str) -> List[str]:
    try:
        raw = json.loads(path)
        if isinstance(raw, list):
            return [str(x) for x in raw]
    except Exception:
        pass
    return []
