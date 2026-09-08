import asyncio
import random
from datetime import datetime

class DisruptionSimulator:
    """Simulates a live IoT disruption feed for demo purposes."""
    
    DISRUPTION_SCENARIOS = [
        {"checkpoint_id": "CP04", "type": "fog", "severity": 0.75, "message": "Dense fog at Khopoli — visibility < 100m"},
        {"checkpoint_id": "CP06", "type": "traffic", "severity": 0.65, "message": "Heavy congestion at Panvel junction"},
        {"checkpoint_id": "CP03", "type": "accident", "severity": 0.85, "message": "Multi-vehicle accident near Talegaon"},
        {"checkpoint_id": "RN01", "type": "strike", "severity": 0.5, "message": "Rail workers delay at Pune station — 45min delay"},
        {"checkpoint_id": "CP07", "type": "flood", "severity": 0.9, "message": "Flash flooding on Vashi bridge — road closure"},
    ]
    
    def __init__(self):
        self.active_disruptions = {}
        self._running = False
    
    async def start(self):
        self._running = True
        asyncio.create_task(self._simulate_loop())
    
    async def _simulate_loop(self):
        while self._running:
            # Random chance of new disruption every 30 seconds
            if random.random() < 0.3:
                scenario = random.choice(self.DISRUPTION_SCENARIOS)
                # Check if this checkpoint already has a disruption to avoid duplicates
                if not any(d['checkpoint_id'] == scenario['checkpoint_id'] for d in self.active_disruptions.values()):
                    disruption = {**scenario, "id": f"DIS_{int(datetime.now().timestamp())}",
                                  "detected_at": datetime.now().isoformat(),
                                  "estimated_duration_min": random.randint(15, 120)}
                    self.active_disruptions[disruption['id']] = disruption
            
            # Random chance of resolving a disruption
            if self.active_disruptions and random.random() < 0.2:
                resolve_id = random.choice(list(self.active_disruptions.keys()))
                del self.active_disruptions[resolve_id]
            
            await asyncio.sleep(30)
    
    def get_active(self) -> list:
        return list(self.active_disruptions.values())
    
    def get_checkpoint_risk(self, checkpoint_id: str) -> float:
        for d in self.active_disruptions.values():
            if d['checkpoint_id'] == checkpoint_id:
                return d['severity']
        return 0.0
        
# Global instance for use in FastAPI app
disruption_simulator = DisruptionSimulator()