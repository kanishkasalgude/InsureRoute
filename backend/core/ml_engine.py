"""Train RandomForest on synthetic CSV, expose predict_risk()"""
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import LabelEncoder
import pickle
import os

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(base_dir, "models", "risk_model.pkl")
ENCODERS_PATH = os.path.join(base_dir, "models", "encoders.pkl")
DATA_PATH = os.path.join(base_dir, "data", "transit_risk.csv")

FEATURES = ['hour_of_day', 'day_of_week', 'weather_code', 'visibility_km',
            'wind_speed_kmh', 'rainfall_mm', 'traffic_density', 
            'checkpoint_type_enc', 'road_condition_enc', 'incident_type_enc']

def train_model():
    df = pd.read_csv(DATA_PATH)
    
    # Add checkpoint_type derived from checkpoint_id
    type_map = {**{f'CP0{i}': 'road' for i in range(1,9)},
                **{f'RN0{i}': 'rail' for i in range(1,5)},
                'PT01': 'port', 'PT02': 'port', 'AP01': 'airport'}
    df['checkpoint_type'] = df['checkpoint_id'].map(type_map).fillna('road')
    
    le_road = LabelEncoder().fit(df['road_condition'])
    le_incident = LabelEncoder().fit(df['incident_type'])
    le_type = LabelEncoder().fit(df['checkpoint_type'])
    
    df['road_condition_enc'] = le_road.transform(df['road_condition'])
    df['incident_type_enc'] = le_incident.transform(df['incident_type'])
    df['checkpoint_type_enc'] = le_type.transform(df['checkpoint_type'])
    
    X = df[FEATURES]
    y = df['risk_score']
    
    model = RandomForestRegressor(n_estimators=100, max_depth=12, random_state=42, n_jobs=-1)
    model.fit(X, y)
    
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    with open(MODEL_PATH, 'wb') as f: pickle.dump(model, f)
    with open(ENCODERS_PATH, 'wb') as f:
        pickle.dump({'road': le_road, 'incident': le_incident, 'type': le_type}, f)
    
    print(f"Model trained. Feature importances: {dict(zip(FEATURES, model.feature_importances_.round(3)))}")
    return model

def predict_risk(checkpoint_id: str, weather_data: dict, hour: int, 
                  day_of_week: int, traffic_density: float = 0.5) -> float:
    if not os.path.exists(MODEL_PATH):
        train_model()
    
    with open(MODEL_PATH, 'rb') as f: model = pickle.load(f)
    with open(ENCODERS_PATH, 'rb') as f: encoders = pickle.load(f)
    
    type_map = {**{f'CP0{i}': 'road' for i in range(1,9)},
                **{f'RN0{i}': 'rail' for i in range(1,5)},
                'PT01': 'port', 'PT02': 'port', 'AP01': 'airport'}
    cp_type = type_map.get(checkpoint_id, 'road')
    
    # Safe label encoding (handle unseen labels)
    def safe_encode(encoder, value, default=0):
        try: return encoder.transform([value])[0]
        except: return default
    
    features = [[
        hour, day_of_week,
        weather_data.get('weather_code', 0),
        weather_data.get('visibility_km', 10),
        weather_data.get('wind_speed_kmh', 15),
        weather_data.get('rainfall_mm', 0),
        traffic_density,
        safe_encode(encoders['type'], cp_type),
        safe_encode(encoders['road'], weather_data.get('road_condition', 'good')),
        safe_encode(encoders['incident'], weather_data.get('incident_type', 'none'))
    ]]
    
    score = float(model.predict(features)[0])
    return round(min(max(score, 0.0), 1.0), 3)

if __name__ == "__main__":
    train_model()