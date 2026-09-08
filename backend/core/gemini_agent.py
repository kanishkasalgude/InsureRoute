import os
import asyncio
import google.generativeai as genai
from typing import Any
from google.ai.generativelanguage import Type
from core.gemini_guard import call_gemini_with_guard

TOOLS = [
    {
        "name": "get_disruptions",
        "description": "Fetch live disruptions at given checkpoint IDs. Returns weather, incidents, and computed risk scores for each checkpoint.",
        "parameters": {
            "type": Type.OBJECT,
            "properties": {
                "checkpoint_ids": {
                    "type": Type.ARRAY,
                    "items": {"type": Type.STRING},
                    "description": "List of checkpoint IDs to check, e.g. ['CP01','CP03','CP06']"
                }
            },
            "required": ["checkpoint_ids"]
        }
    },
    {
        "name": "score_route",
        "description": "Compute composite risk score (0-1) for an entire route, factoring in all checkpoints, cargo type, and current conditions.",
        "parameters": {
            "type": Type.OBJECT,
            "properties": {
                "route_id": {"type": Type.STRING, "description": "The route identifier"},
                "cargo_type": {"type": Type.STRING, "description": "Type of cargo e.g. 'pharmaceuticals'"},
                "cargo_value_inr": {"type": Type.NUMBER, "description": "Value of cargo in INR"}
            },
            "required": ["route_id", "cargo_type"]
        }
    },
    {
        "name": "calculate_premium",
        "description": "Calculate dynamic insurance premium for a shipment on a specific route. Returns base premium, risk loading, and final premium in INR.",
        "parameters": {
            "type": Type.OBJECT,
            "properties": {
                "route_id": {"type": Type.STRING},
                "cargo_type": {"type": Type.STRING},
                "cargo_value_inr": {"type": Type.NUMBER},
                "coverage_type": {
                    "type": Type.STRING,
                    "enum": ["basic", "comprehensive", "all_risk"],
                    "description": "Level of insurance coverage"
                }
            },
            "required": ["route_id", "cargo_type", "cargo_value_inr", "coverage_type"]
        }
    },
    {
        "name": "trigger_reroute",
        "description": "Find the optimal alternative route avoiding specified problematic checkpoints. Returns new route with estimated time, cost, and risk score.",
        "parameters": {
            "type": Type.OBJECT,
            "properties": {
                "origin": {"type": Type.STRING},
                "destination": {"type": Type.STRING},
                "avoid_checkpoints": {
                    "type": Type.ARRAY,
                    "items": {"type": Type.STRING},
                    "description": "Checkpoint IDs to avoid due to disruptions"
                },
                "cargo_type": {"type": Type.STRING},
                "priority": {
                    "type": Type.STRING,
                    "enum": ["speed", "cost", "safety"],
                    "description": "What to optimise for"
                }
            },
            "required": ["origin", "destination", "cargo_type", "priority"]
        }
    },
    {
        "name": "get_multimodal_options",
        "description": "Get all available multi-modal route options (road, rail, air, sea combinations) between origin and destination.",
        "parameters": {
            "type": Type.OBJECT,
            "properties": {
                "origin": {"type": Type.STRING},
                "destination": {"type": Type.STRING},
                "cargo_weight_tons": {"type": Type.NUMBER},
                "cargo_type": {"type": Type.STRING},
                "deadline_hours": {"type": Type.NUMBER, "description": "Hard delivery deadline in hours from now"}
            },
            "required": ["origin", "destination", "cargo_type"]
        }
    },
    {
        "name": "get_weather_forecast",
        "description": "Get 6-hour weather forecast for a specific location. Use to proactively warn about upcoming conditions.",
        "parameters": {
            "type": Type.OBJECT,
            "properties": {
                "lat": {"type": Type.NUMBER},
                "lon": {"type": Type.NUMBER},
                "hours_ahead": {"type": Type.INTEGER, "description": "How many hours to forecast (1-72)"}
            },
            "required": ["lat", "lon"]
        }
    }
]

SYSTEM_PROMPT = """You are InsureRoute's AI Operations Brain. You are an expert logistics risk manager and insurance analyst with deep knowledge of Indian supply chains.

Your job is to ACTIVELY manage shipment risk — not just report it. You have tools to:
1. Check live disruptions at any checkpoint
2. Score entire routes for risk
3. Calculate dynamic insurance premiums
4. Trigger reroutes when risk crosses thresholds
5. Compare multi-modal transport options
6. Forecast weather impacts

DECISION RULES:
- If any checkpoint risk score > 0.7: ALWAYS call trigger_reroute proactively
- If route risk > 0.6 AND cargo is pharmaceuticals/perishables: Escalate to all_risk coverage
- If ETA delay > 2 hours: Compare multimodal options
- Always call calculate_premium AFTER scoring route, so the user sees updated pricing

RESPONSE FORMAT:
- Be concise and decisive. Give your recommendation first.
- Quantify everything: "risk score 0.73", "₹12,400 premium", "42-min delay"
- End with one clear action item for the dispatcher.

You are the orchestrator. Use your tools before responding."""

class GeminiAgent:
    def __init__(self, tool_executors: dict):
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel(
                model_name="gemini-2.5-flash",
                tools=TOOLS,
                system_instruction=SYSTEM_PROMPT
            )
        else:
            self.model = None
            
        self.tool_executors = tool_executors  # Dict mapping tool_name → async function
    
    async def run(self, user_message: str, context: dict = {}) -> dict:
        """Agentic loop: Gemini calls tools until it has enough info to respond."""
        if not self.model:
            return {
                "response": "Gemini API key is not configured. Returning fallback rule-based analysis.",
                "tools_invoked": [],
                "model": "fallback"
            }
            
        chat = self.model.start_chat()
        full_context = f"SHIPMENT CONTEXT: {context}\n\nUSER REQUEST: {user_message}"
        
        try:
            response = call_gemini_with_guard(full_context, lambda: chat.send_message(full_context))
            
            # Agentic loop: process tool calls
            max_iterations = 5
            tools_used = []
            
            for _ in range(max_iterations):
                tool_calls = [p for p in response.parts if hasattr(p, 'function_call') and p.function_call]
                if not tool_calls:
                    break
                
                tool_results = []
                for part in response.parts:
                    if hasattr(part, 'function_call') and part.function_call:
                        fc = part.function_call
                        tools_used.append({"name": fc.name, "args": dict(fc.args)})
                        
                        executor = self.tool_executors.get(fc.name)
                        if executor:
                            # If async or sync
                            if asyncio.iscoroutinefunction(executor):
                                result = await executor(**dict(fc.args))
                            else:
                                result = executor(**dict(fc.args))
                                
                            tool_results.append({
                                "function_response": {
                                    "name": fc.name,
                                    "response": {"result": result}
                                }
                            })
                
                if tool_results:
                    response = call_gemini_with_guard(
                        f"{user_message}-tool-loop-{len(tools_used)}",
                        lambda: chat.send_message(tool_results),
                    )
            
            # Extract final text response
            final_text = "".join(p.text for p in response.parts if hasattr(p, 'text') and p.text)
            
            return {
                "response": final_text,
                "tools_invoked": tools_used,
                "model": "gemini-2.5-flash"
            }
        except Exception as e:
            return {
                "response": f"AI advisory currently unavailable: {str(e)}",
                "tools_invoked": [],
                "model": "fallback"
            }

async def analyze_weather_image(image_base64: str, route_context: dict) -> str:
    """Gemini analyzes a weather radar screenshot for route impact."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
         return "Gemini API key is not configured. Cannot analyze image."
         
    model = genai.GenerativeModel("gemini-2.5-flash")
    try:
        payload = [
            {
                "role": "user",
                "parts": [
                    {"inline_data": {"mime_type": "image/jpeg", "data": image_base64}},
                    {"text": f"This is a weather radar image. Our cargo route is: {route_context}. "
                             f"Identify any weather systems that could impact this route and estimate severity (0-1). "
                             f"Be specific about which checkpoints are affected."}
                ]
            }
        ]
        response = call_gemini_with_guard(
            f"image-analysis-{str(route_context)}",
            lambda: model.generate_content(payload),
        )
        return response.text
    except Exception as e:
        return f"Failed to analyze image: {str(e)}"