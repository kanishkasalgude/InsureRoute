import networkx as nx
import json
import os
import random
from datetime import datetime

def build_multimodal_graph(topology_path: str, 
                            blocked_checkpoints: list = None,
                            cargo_weight_tons: float = 1.0,
                            cargo_type: str = "fmcg") -> nx.DiGraph:
    if blocked_checkpoints is None:
        blocked_checkpoints = []
    
    G = nx.Graph()
    with open(topology_path, encoding="utf-8") as f:
        topo = json.load(f)
    
    # Add nodes
    for node in topo['nodes']:
        if node['id'] not in blocked_checkpoints:
            G.add_node(node['id'], **node)
    
    # Load multimodal config
    config_path = os.path.join(os.path.dirname(topology_path), "multimodal_config.json")
    with open(config_path, encoding="utf-8") as f:
        modal_config = json.load(f)
        
    cargo_path = os.path.join(os.path.dirname(topology_path), "cargo_types.json")
    with open(cargo_path, encoding="utf-8") as f:
        cargo_types = {c["id"]: c for c in json.load(f)["types"]}
    
    # Add edges with cost weights
    for edge in topo['edges']:
        if edge['from'] in G.nodes and edge['to'] in G.nodes:
            mode = edge['mode']
            mode_cfg = modal_config['modes'].get(mode, {})
            
            # Check cargo constraints
            max_weight = mode_cfg.get('max_cargo_weight_tons', 999)
            if cargo_weight_tons > max_weight:
                continue  # Skip this edge — cargo too heavy
            
            # Check hazmat
            if cargo_type == 'chemicals' and mode == 'rail':
                continue  # Hazmat restriction
            
            # Check cold chain
            cargo_cfg = cargo_types.get(cargo_type, {})
            if cargo_cfg.get('requires_cold_chain') and mode == 'sea':
                continue  # No cold chain on sea for this config
            
            # Weight = time + cost component + mode transfer penalty
            cost_km = mode_cfg.get('cost_per_km_inr', 35)
            time_weight = edge['base_time_min']
            cost_weight = edge['distance_km'] * cost_km / 1000  # Normalized
            
            # Additional risk weight could be dynamically calculated and updated here
            # We initialize risk_weight same as time_weight initially
            
            G.add_edge(
                edge['from'], edge['to'],
                mode=mode,
                distance_km=edge['distance_km'],
                base_time_min=edge['base_time_min'],
                cost_inr=edge['distance_km'] * cost_km,
                co2_kg=edge['distance_km'] * mode_cfg.get('co2_per_km_kg', 0.27),
                weight=time_weight + cost_weight,
                risk_weight=time_weight # Placeholder for safety priority
            )
    
    return G

def find_optimal_routes(origin: str, destination: str, 
                         blocked: list = None,
                         priority: str = "speed",
                         top_k: int = 5,
                         cargo_type: str = "fmcg",
                         cargo_weight_tons: float = 1.0) -> list[dict]:
    if blocked is None:
        blocked = []
        
    topology_path = os.path.join(os.path.dirname(__file__), "..", "data", "graph_topology.json")
    G = build_multimodal_graph(topology_path, blocked, cargo_weight_tons, cargo_type)
    
    # Weight function based on priority
    weight_fn = {
        "speed": "base_time_min",
        "cost": "cost_inr", 
        "safety": "risk_weight"
    }.get(priority, "base_time_min")
    
    try:
        # Get up to 20 simple paths to evaluate
        path_gen = nx.shortest_simple_paths(G, origin, destination, weight=weight_fn)
        paths = []
        for _ in range(20):
            try:
                paths.append(next(path_gen))
            except StopIteration:
                break
    except nx.NetworkXNoPath:
        return []  # Edge case: no path
    
    routes = []
    config_path = os.path.join(os.path.dirname(topology_path), "multimodal_config.json")
    with open(config_path, encoding="utf-8") as f:
        modal_config = json.load(f)
        
    for i, path in enumerate(paths):
        edges = [G[path[j]][path[j+1]] for j in range(len(path)-1)]
        modes_used = list(dict.fromkeys(e['mode'] for e in edges))  # Ordered unique modes
        
        # Count mode transfers
        transfers = sum(1 for j in range(len(edges)-1) if edges[j]['mode'] != edges[j+1]['mode'])
        
        # Transfer penalties
        transfer_cost = 0
        transfer_time = 0
        
        for j in range(len(edges)-1):
            if edges[j]['mode'] != edges[j+1]['mode']:
                key = f"{edges[j]['mode']}_to_{edges[j+1]['mode']}"
                penalty = modal_config['transfer_penalties'].get(key, {})
                transfer_time += penalty.get('time_min', 60)
                transfer_cost += penalty.get('cost_inr', 2000)
        
        total_time = sum(e['base_time_min'] for e in edges) + transfer_time
        total_cost = sum(e['cost_inr'] for e in edges) + transfer_cost
        total_distance = sum(e['distance_km'] for e in edges)
        total_co2 = sum(e['co2_kg'] for e in edges)
        
        # --- DYNAMIC COST CALCULATION ---
        # 1. Cargo-type surcharge (+5% to +25%)
        cargo_surcharge = 0.0
        cargo_driver = ""
        if cargo_type in ['chemicals', 'automotive', 'pharmaceuticals']:
            cargo_surcharge = random.uniform(0.05, 0.25)
            cargo_driver = "Cargo Premium"
            
        # 2. Route distance tier volatility
        volatility = 0.15
        if total_distance < 200:
            volatility = 0.20
            distance_driver = "Short-Haul Volatility"
        elif total_distance > 500:
            volatility = 0.08
            distance_driver = "Long-Haul Contract"
        else:
            distance_driver = "Spot Rate"
            
        market_surge = random.uniform(-volatility, volatility)
        
        # 3. Time-of-day / Rush Hour
        hour = datetime.now().hour
        rush_hour_surge = 0.0
        if 8 <= hour <= 10 or 17 <= hour <= 19:
            rush_hour_surge = random.uniform(0.08, 0.15)
            time_driver = "Rush Hour"
        else:
            time_driver = ""

        # Determine main driver
        total_surge_pct = cargo_surcharge + market_surge + rush_hour_surge
        
        if cargo_surcharge > abs(market_surge) and cargo_surcharge > rush_hour_surge:
            driver = cargo_driver
        elif rush_hour_surge > abs(market_surge):
            driver = time_driver
        else:
            driver = distance_driver
            
        if total_surge_pct > 0.10:
            label = "High Demand Surge"
        elif total_surge_pct < -0.05:
            label = "Favorable Market Rate"
        else:
            label = "Standard Spot Rate"
            
        total_cost = total_cost * (1 + total_surge_pct)
        
        market_trend = {
            "label": label,
            "delta_pct": round(total_surge_pct * 100, 1),
            "driver": driver
        }
        
        routes.append({
            "route_id": f"ROUTE_{chr(65+i)}",
            "path": path,
            "modes": modes_used,
            "is_multimodal": len(modes_used) > 1,
            "transfers": transfers,
            "total_time_min": total_time,
            "total_cost_inr": round(total_cost, 2),
            "total_distance_km": round(total_distance, 2),
            "total_co2_kg": round(total_co2, 2),
            "market_trend": market_trend,
            "checkpoints": [n for n in path if n.startswith('CP') or n.startswith('RN') or n.startswith('PT') or n.startswith('AP')]
        })
    
    # Sort the evaluated routes based on priority
    if priority == "speed":
        routes.sort(key=lambda x: x["total_time_min"])
    elif priority == "cost":
        routes.sort(key=lambda x: x["total_cost_inr"])
    else:
        # Default safety/time combo
        routes.sort(key=lambda x: x["total_time_min"] + (x["transfers"] * 30))

    # Re-assign route IDs so the best is always ROUTE_A
    for i, r in enumerate(routes):
        r["route_id"] = f"ROUTE_{chr(65+i)}"

    # Filter out illogical routes that are > 2.5x worse than the best route
    if not routes:
        return []
        
    best_time = routes[0]["total_time_min"]
    best_cost = routes[0]["total_cost_inr"]
    
    valid_routes = []
    for r in routes:
        # If a route is more than 2.5x the time AND 2.5x the cost, it's illogical
        if r["total_time_min"] <= best_time * 2.5 or r["total_cost_inr"] <= best_cost * 2.5:
            valid_routes.append(r)
            
    return valid_routes[:top_k]