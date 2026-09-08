"""
graph_engine.py — NetworkX supply-chain graph with Dijkstra rerouting.

Builds a 50-node graph seeded from actual hub names in the CSV.
On disruption, blocked edge weight → 999 and Dijkstra finds alternate path.
"""

import networkx as nx
import random
import numpy as np
from typing import Optional

# Canonical list of 50 hubs extracted from the CSV dataset
HUBS = [
    "Madurai_DC", "Rajahmundry_DC", "Ludhiana_DC", "Noida_DC", "Indore_Hub",
    "Chennai_Hub", "Guntur_DC", "Amritsar_DC", "Ahmedabad_Hub", "Belgaum_DC",
    "Navi_Mumbai_DC", "Mumbai_Hub", "Delhi_Hub", "Pune_Hub", "Hyderabad_Hub",
    "Visakhapatnam_Hub", "Siliguri_DC", "Kolkata_Hub", "Nagpur_Hub",
    "Bhopal_Hub", "Raipur_DC", "Lucknow_Hub", "Udaipur_DC", "Chandigarh_DC",
    "Tiruchirappalli_DC", "Hubli_DC", "Gurgaon_DC", "Jaipur_Hub",
    "Bangalore_Hub", "Patna_Hub", "Kochi_Hub", "Surat_Hub", "Vadodara_Hub",
    "Nashik_Hub", "Coimbatore_Hub", "Vijayawada_DC", "Salem_DC",
    "Ghaziabad_DC", "Faridabad_DC", "Bhubaneswar_DC", "Ranchi_DC",
    "Kanpur_DC", "Varanasi_DC", "Jodhpur_DC", "Mysore_DC", "Thane_DC",
    "Mangalore_DC", "Allahabad_DC", "Guwahati_DC", "Agra_DC",
]


def build_graph(seed: int = 42) -> nx.DiGraph:
    """Construct the supply chain graph with realistic Indian geography weights."""
    rng = random.Random(seed)
    G = nx.DiGraph()
    G.add_nodes_from(HUBS)
    
    import math
    def haversine(lon1, lat1, lon2, lat2):
        R = 6371  # radius of Earth in km
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)
        a = math.sin(delta_phi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        return R * c

    positions = get_node_positions()

    # Connect every hub to 4–7 nearest neighbours based on actual geography
    for i, src in enumerate(HUBS):
        src_pos = positions[src]
        
        # Calculate distances to all other hubs
        distances = []
        for dst in HUBS:
            if src != dst:
                dst_pos = positions[dst]
                dist = haversine(src_pos[0], src_pos[1], dst_pos[0], dst_pos[1])
                distances.append((dist, dst))
                
        # Sort by distance to find nearest neighbours
        distances.sort(key=lambda x: x[0])
        
        n_edges = rng.randint(4, 7)
        targets = distances[:n_edges]
        
        for dist, dst in targets:
            dist = max(10, int(dist)) # avoid 0 distance
            time = round(dist / rng.uniform(40, 80), 1)   # hrs
            cost = round(dist * rng.uniform(15, 35), 0)   # ₹
            G.add_edge(src, dst, distance=dist, time=time, cost=cost, weight=time)
            # ensure reverse edge exists (bidirectional logistics)
            if not G.has_edge(dst, src):
                G.add_edge(dst, src, distance=dist, time=time, cost=cost, weight=time)

    return G


# Module-level singleton graph
_GRAPH: Optional[nx.DiGraph] = None


def get_graph() -> nx.DiGraph:
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_graph()
    return _GRAPH


def find_route(
    origin: str,
    destination: str,
    disrupted_edge: Optional[tuple] = None,
) -> dict:
    """
    Find the best (Dijkstra) route from origin → destination.

    Parameters
    ----------
    origin, destination : hub names
    disrupted_edge      : (src, dst) tuple to block (weight → 999)

    Returns
    -------
    dict with keys: path, total_time, total_cost, total_distance, rerouted
    """
    G = get_graph()

    # Ensure nodes exist
    if origin not in G.nodes:
        origin = HUBS[0]
    if destination not in G.nodes:
        destination = HUBS[1]

    rerouted = False
    if disrupted_edge and G.has_edge(*disrupted_edge):
        original_weight = G[disrupted_edge[0]][disrupted_edge[1]]["weight"]
        G[disrupted_edge[0]][disrupted_edge[1]]["weight"] = 999
        rerouted = True

    try:
        path = nx.dijkstra_path(G, origin, destination, weight="weight")
        total_time = sum(G[path[i]][path[i + 1]]["time"] for i in range(len(path) - 1))
        total_dist = sum(G[path[i]][path[i + 1]]["distance"] for i in range(len(path) - 1))
        total_cost = sum(G[path[i]][path[i + 1]]["cost"] for i in range(len(path) - 1))
    except nx.NetworkXNoPath:
        path = [origin, destination]
        total_time = 999
        total_dist = 9999
        total_cost = 999999
    finally:
        if disrupted_edge and rerouted and G.has_edge(*disrupted_edge):
            G[disrupted_edge[0]][disrupted_edge[1]]["weight"] = original_weight

    return {
        "path": path,
        "total_time_hrs": round(total_time, 1),
        "total_distance_km": round(total_dist, 1),
        "total_cost_inr": round(total_cost, 0),
        "hops": len(path) - 1,
        "rerouted": rerouted,
    }


def get_node_positions() -> dict:
    """Approximate lon/lat positions for plotting (Indian geography)."""
    positions = {
        "Delhi_Hub":         (77.1, 28.7),
        "Mumbai_Hub":        (72.8, 19.1),
        "Bangalore_Hub":     (77.6, 12.9),
        "Chennai_Hub":       (80.3, 13.1),
        "Kolkata_Hub":       (88.4, 22.6),
        "Hyderabad_Hub":     (78.5, 17.4),
        "Pune_Hub":          (73.9, 18.5),
        "Ahmedabad_Hub":     (72.6, 23.0),
        "Jaipur_Hub":        (75.8, 26.9),
        "Lucknow_Hub":       (80.9, 26.8),
        "Kochi_Hub":         (76.3, 10.0),
        "Coimbatore_Hub":    (77.0, 11.0),
        "Nagpur_Hub":        (79.1, 21.1),
        "Bhopal_Hub":        (77.4, 23.3),
        "Indore_Hub":        (75.9, 22.7),
        "Surat_Hub":         (72.8, 21.2),
        "Vadodara_Hub":      (73.2, 22.3),
        "Nashik_Hub":        (73.8, 20.0),
        "Visakhapatnam_Hub": (83.3, 17.7),
        "Patna_Hub":         (85.1, 25.6),
        "Gurgaon_DC":        (77.0, 28.5),
        "Noida_DC":          (77.3, 28.6),
        "Ghaziabad_DC":      (77.4, 28.7),
        "Faridabad_DC":      (77.3, 28.4),
        "Thane_DC":          (73.0, 19.2),
        "Navi_Mumbai_DC":    (73.0, 19.0),
        "Amritsar_DC":       (74.9, 31.6),
        "Ludhiana_DC":       (75.9, 30.9),
        "Chandigarh_DC":     (76.8, 30.7),
        "Jodhpur_DC":        (73.0, 26.3),
        "Udaipur_DC":        (73.7, 24.6),
        "Agra_DC":           (78.0, 27.2),
        "Varanasi_DC":       (83.0, 25.3),
        "Kanpur_DC":         (80.3, 26.5),
        "Allahabad_DC":      (81.8, 25.4),
        "Ranchi_DC":         (85.3, 23.4),
        "Raipur_DC":         (81.6, 21.3),
        "Bhubaneswar_DC":    (85.8, 20.3),
        "Siliguri_DC":       (88.4, 26.7),
        "Guwahati_DC":       (91.7, 26.2),
        "Madurai_DC":        (78.1, 9.9),
        "Tiruchirappalli_DC":(78.7, 10.8),
        "Salem_DC":          (78.2, 11.6),
        "Coimbatore_Hub":    (77.0, 11.0),
        "Mangalore_DC":      (74.9, 12.9),
        "Hubli_DC":          (75.1, 15.4),
        "Belgaum_DC":        (74.5, 15.9),
        "Vijayawada_DC":     (80.6, 16.5),
        "Guntur_DC":         (80.5, 16.3),
        "Rajahmundry_DC":    (81.8, 17.0),
        "Mysore_DC":         (76.6, 12.3),
    }
    # Fill any missing hubs with generic positions
    import random as _r
    _r.seed(99)
    for hub in HUBS:
        if hub not in positions:
            positions[hub] = (
                _r.uniform(72, 92),
                _r.uniform(8, 32),
            )
    return positions
