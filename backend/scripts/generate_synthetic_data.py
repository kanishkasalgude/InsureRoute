# Synthetic data generation script: scripts/generate_synthetic_data.py
import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta
import os

np.random.seed(42)
N = 30000
checkpoints = ['CP01','CP02','CP03','CP04','CP05','CP06','CP07','CP08',
                'RN01','RN02','RN03','RN04','PT01','PT02','AP01']
incident_types = ['none','none','none','none','accident','flood','fog',
                  'road_closure','strike','mechanical']

records = []
base_date = datetime(2024, 1, 1)
for i in range(N):
    cp = random.choice(checkpoints)
    dt = base_date + timedelta(hours=random.randint(0, 8760))
    hour = dt.hour
    month = dt.month
    monsoon = 1.4 if 6 <= month <= 9 else 1.0
    peak = 1.6 if hour in range(8,10) or hour in range(17,20) else 1.0
    rainfall = np.random.exponential(2) * monsoon
    wind = np.random.normal(20, 10) * monsoon
    visibility = max(0.5, 10 - rainfall * 0.8 + np.random.normal(0, 1))
    traffic = min(1, np.random.beta(2, 5) * peak)
    delay = np.random.exponential(15) * traffic * monsoon
    weather_code = int(np.random.choice([0,1,2,3,61,63,65,80,95], p=[.3,.15,.1,.1,.1,.07,.05,.08,.05]))
    road_cond = random.choice(['good','moderate','poor','very_poor'])
    incident = random.choice(incident_types)
    risk = min(1.0, 0.3*(rainfall/20) + 0.25*traffic + 0.25*(delay/120) + 0.2*(0 if incident=='none' else 1))
    records.append([cp, dt.strftime('%Y-%m-%d %H:%M'), hour, dt.weekday(),
                    weather_code, round(visibility,2), round(wind,2),
                    round(rainfall,2), road_cond, round(delay,2),
                    round(traffic,3), incident, round(risk,3)])

df = pd.DataFrame(records, columns=['checkpoint_id','timestamp','hour_of_day',
    'day_of_week','weather_code','visibility_km','wind_speed_kmh','rainfall_mm',
    'road_condition','historical_delay_min','traffic_density','incident_type','risk_score'])

os.makedirs('data', exist_ok=True)
df.to_csv('data/transit_risk.csv', index=False)
print("Generated", N, "records")