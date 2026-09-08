from fastapi import FastAPI, WebSocket, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import json
import uuid
import os
import asyncio
from datetime import datetime
from dotenv import load_dotenv

from models.schemas import ShipmentCreate, RouteAnalysisRequest, RouteRerouteRequest, InsuranceQuoteRequest, ChatMessage
from core.graph_router import find_optimal_routes
from core.insurance_engine import calculate_dynamic_premium
from core.ml_engine import predict_risk
from core.disruption_feed import disruption_simulator
from core.gemini_agent import GeminiAgent, analyze_weather_image
from legacy.api import legacy_router, _initialize, _weather_polling_loop, live_weather_state

load_dotenv()

app = FastAPI(title="InsureRoute API", version="1.0")

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(legacy_router, prefix="/api/v1")

# In-memory store for demo
shipments_db = {}

# Setup agent tools
def get_disruptions_tool(checkpoint_ids: list):
    active = disruption_simulator.get_active()
    return [d for d in active if d['checkpoint_id'] in checkpoint_ids]

def score_route_tool(route_id: str, cargo_type: str, cargo_value_inr: float = 0, checkpoints: list = None) -> float:
    """
    Dynamic risk scoring using:
    1. ML RandomForest predictions on each route checkpoint
    2. Live IoT disruption severity blended in
    3. Live OpenWeatherMap weather severity
    """
    import math

    now = datetime.now()
    hour = now.hour
    day_of_week = now.weekday()

    route_checkpoints = checkpoints or ["Pune_Hub", "Mumbai_Hub"]

    # Derive weather inputs from live state
    from legacy.weather_service import fetch_route_weather
    weather_state = fetch_route_weather(route_checkpoints)
    
    worst_weather_severity = 0.0
    checkpoint_weather = {}
    for cp in weather_state.get("checkpoints", []):
        checkpoint_weather[cp["name"]] = {
            "weather_code": cp.get("weather_id", 800),
            "visibility_km": max(0.1, 10 - cp.get("rain_1h", 0) * 2),  # Estimate from rain
            "wind_speed_kmh": cp.get("wind_speed", 0) * 3.6,  # m/s → km/h
            "rainfall_mm": cp.get("rain_1h", 0),
        }
        if cp.get("is_dangerous"):
            worst_weather_severity = max(worst_weather_severity, cp.get("severity", 0))

    # Build representative weather dict for ML (use worst live checkpoint or defaults)
    ml_weather = {
        "weather_code": weather_state.get("checkpoints", [{}])[0].get("weather_id", 800) if weather_state.get("checkpoints") else 800,
        "visibility_km": 8.0 if worst_weather_severity < 0.3 else max(1.0, 8.0 - worst_weather_severity * 10),
        "wind_speed_kmh": worst_weather_severity * 40,  # Scale severity → wind speed
        "rainfall_mm": worst_weather_severity * 8,
        "road_condition": "poor" if worst_weather_severity > 0.5 else "moderate" if worst_weather_severity > 0.2 else "good",
        "incident_type": "none",
    }

    # Score each checkpoint on the route using the ML model
    ml_scores = []
    for cp_id in route_checkpoints:
        try:
            score = predict_risk(
                checkpoint_id=cp_id,
                weather_data=ml_weather,
                hour=hour,
                day_of_week=day_of_week,
                traffic_density=0.6 if (8 <= hour <= 10 or 17 <= hour <= 19) else 0.3,
            )
            ml_scores.append(score)
        except Exception:
            ml_scores.append(0.3)  # Safe default on ML failure

    # Average ML score across all checkpoints
    ml_avg = sum(ml_scores) / len(ml_scores) if ml_scores else 0.3

    # Blend with live disruption severity for checkpoints on this route
    active_disruptions = disruption_simulator.get_active()
    max_disruption_severity = 0.0
    for d in active_disruptions:
        if not route_checkpoints or d["checkpoint_id"] in route_checkpoints:
            max_disruption_severity = max(max_disruption_severity, d["severity"])

    # Final composite score:
    # 60% ML model + 25% live disruptions + 15% live weather
    composite = (
        ml_avg * 0.60
        + max_disruption_severity * 0.25
        + worst_weather_severity * 0.15
    )
    return round(min(max(composite, 0.0), 1.0), 3)

def calculate_premium_tool(route_id: str, cargo_type: str, cargo_value_inr: float, coverage_type: str):
    score = score_route_tool(route_id, cargo_type)
    return calculate_dynamic_premium(score, cargo_type, cargo_value_inr, coverage_type, ["road"])

def trigger_reroute_tool(origin: str, destination: str, avoid_checkpoints: list, cargo_type: str, priority: str):
    routes = find_optimal_routes(origin, destination, blocked=avoid_checkpoints, priority=priority, cargo_type=cargo_type)
    if routes:
        return routes[0]
    return {"error": "No alternative routes available."}

def get_multimodal_options_tool(origin: str, destination: str, cargo_weight_tons: float, cargo_type: str, deadline_hours: int = 0):
    return find_optimal_routes(origin, destination, cargo_type=cargo_type, cargo_weight_tons=cargo_weight_tons)

def get_weather_forecast_tool(lat: float, lon: float, hours_ahead: int = 6):
    return {"weather_code": 3, "visibility_km": 5.5, "wind_speed_kmh": 20, "rainfall_mm": 2.1}

tool_executors = {
    "get_disruptions": get_disruptions_tool,
    "score_route": score_route_tool,
    "calculate_premium": calculate_premium_tool,
    "trigger_reroute": trigger_reroute_tool,
    "get_multimodal_options": get_multimodal_options_tool,
    "get_weather_forecast": get_weather_forecast_tool
}

agent = GeminiAgent(tool_executors)

@app.on_event("startup")
async def startup_event():
    await disruption_simulator.start()
    # Do not block boot on heavy ML warm-up; Cloud Run requires fast startup.
    asyncio.create_task(asyncio.to_thread(_initialize))
    asyncio.create_task(_weather_polling_loop())

@app.get("/health")
def health_check():
    return {"status": "healthy"}

@app.get("/")
def root():
    return {
        "service": "InsureRoute API",
        "status": "running",
        "docs": "/docs",
        "health": "/health",
    }

@app.get("/api/v1/nodes")
def get_nodes():
    path = os.path.join(os.path.dirname(__file__), "data", "graph_topology.json")
    with open(path, encoding="utf-8") as f:
        return [{"id": n["id"], "name": n["name"], "lat": n["lat"], "lon": n["lon"]} for n in json.load(f)["nodes"]]

@app.get("/api/v1/cargo-types")
def get_cargo_types():
    path = os.path.join(os.path.dirname(__file__), "data", "cargo_types.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)

@app.post("/api/v1/shipments/create")
def create_shipment(shipment: ShipmentCreate):
    ship_id = f"SHP_{str(uuid.uuid4())[:8].upper()}"
    routes = find_optimal_routes(
        shipment.origin, 
        shipment.destination, 
        priority=shipment.priority,
        cargo_type=shipment.cargo_type,
        cargo_weight_tons=shipment.cargo_weight_tons
    )
    
    shipments_db[ship_id] = {
        "id": ship_id,
        "details": shipment.dict(),
        "routes": routes,
        "status": "pending",
        "current_route": None,
        "current_checkpoint": shipment.origin,
        "progress_pct": 0
    }
    
    return {
        "shipment_id": ship_id,
        "options": routes,
        "cargo_value_inr": shipment.cargo_value_inr,
        "cargo_type": shipment.cargo_type,
    }

@app.get("/api/v1/routes/{id}/options")
def get_route_options(id: str):
    if id not in shipments_db:
        raise HTTPException(status_code=404, detail="Shipment not found")
    return shipments_db[id]["routes"]

@app.post("/api/v1/insurance/quote")
def quote_insurance(req: InsuranceQuoteRequest):
    # Extract route checkpoints from the stored shipment if available
    checkpoints = None
    if req.route_id in shipments_db:
        routes = shipments_db[req.route_id].get("routes", [])
        if routes:
            # Get checkpoints from the first (best) route
            checkpoints = routes[0].get("checkpoints", [])
    
    # Dynamic ML + live disruption + live weather risk score
    score = score_route_tool(req.route_id, req.cargo_type, req.cargo_value_inr, checkpoints)
    result = calculate_dynamic_premium(score, req.cargo_type, req.cargo_value_inr, req.coverage_type, ["road"])
    # Include the live risk score for frontend visibility
    result["live_risk_score"] = score
    result["scored_at"] = datetime.now().isoformat()
    return result

@app.post("/api/v1/gemini/chat")
async def chat_with_agent(req: ChatMessage):
    context = {"cargo_type": "standard", "priority": "standard"}
    
    if req.shipment_id and req.shipment_id in shipments_db:
        shipment = shipments_db[req.shipment_id]
        context = {"cargo_type": shipment["details"]["cargo_type"], "priority": shipment["details"]["priority"]}
    
    if req.image_base64:
        # User uploaded an image
        img_response = await analyze_weather_image(req.image_base64, context)
        return {"response": img_response, "tools_invoked": []}
    
    result = await agent.run(req.message, context)
    return result

@app.get("/api/v1/disruptions/live")
def get_live_disruptions():
    return disruption_simulator.get_active()

@app.websocket("/ws/monitor/{shipment_id}")
async def monitor_websocket(websocket: WebSocket, shipment_id: str):
    await websocket.accept()
    if shipment_id not in shipments_db:
        await websocket.close(code=1008)
        return
        
    try:
        while True:
            shipment = shipments_db.get(shipment_id)
            disruptions = disruption_simulator.get_active()
            
            # Dummy progression
            if shipment["progress_pct"] < 100:
                shipment["progress_pct"] += 5
                
            payload = {
                "type": "position_update",
                "shipment_id": shipment_id,
                "current_checkpoint": shipment.get("current_checkpoint"),
                "progress_pct": shipment.get("progress_pct", 0),
                "active_disruptions": disruptions,
                "timestamp": datetime.now().isoformat()
            }
            await websocket.send_text(json.dumps(payload))
            await asyncio.sleep(5)
    except Exception:
        pass

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)