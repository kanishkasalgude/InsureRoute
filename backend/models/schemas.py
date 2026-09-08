from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class ShipmentCreate(BaseModel):
    origin: str
    destination: str
    cargo_type: str
    cargo_value_inr: float
    cargo_weight_tons: float
    priority: str = "speed"
    transport_preference: str = "any"
    deadline: Optional[str] = None

class RouteAnalysisRequest(BaseModel):
    shipment_id: str
    route_id: str
    
class RouteRerouteRequest(BaseModel):
    shipment_id: str
    avoid_checkpoints: List[str]
    priority: str = "safety"
    
class InsuranceQuoteRequest(BaseModel):
    route_id: str
    cargo_type: str
    cargo_value_inr: float
    coverage_type: str
    
class ChatMessage(BaseModel):
    shipment_id: Optional[str] = None
    message: str
    image_base64: Optional[str] = None