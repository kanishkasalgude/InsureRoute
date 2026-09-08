import sys
import os
sys.path.append(os.path.dirname(__file__))

from main import create_shipment
from models.schemas import ShipmentCreate

try:
    shipment = ShipmentCreate(
        origin="AP01",
        destination="CP02",
        cargo_type="fmcg",
        cargo_value_inr=50000000,
        cargo_weight_tons=20.0,
        priority="safety",
        transport_preference="any"
    )
    result = create_shipment(shipment)
    print("Success:", result)
except Exception as e:
    import traceback
    traceback.print_exc()