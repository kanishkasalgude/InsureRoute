import requests
import json

# 1. Create shipment
res = requests.post("http://localhost:8000/api/v1/shipments/create", json={
    "origin": "AP01", 
    "destination": "CP02", 
    "cargo_type": "fmcg", 
    "cargo_value_inr": 5000000, 
    "cargo_weight_tons": 20, 
    "priority": "safety", 
    "transport_preference": "any"
})
print("Create:", res.status_code, res.text)
shipment_id = res.json()["shipment_id"]

# 2. Chat
chat_res = requests.post("http://localhost:8000/api/v1/gemini/chat", json={
    "shipment_id": shipment_id,
    "message": "optimize"
})
print("Chat:", chat_res.status_code, chat_res.text)
