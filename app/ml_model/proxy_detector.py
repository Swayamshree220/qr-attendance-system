import pandas as pd
from sklearn.ensemble import IsolationForest
import joblib
import os
import numpy as np
from datetime import datetime, timedelta
import math

proxy_model = None
MODEL_PATH = os.path.join(os.path.dirname(__file__), 'proxy_detector_model.pkl')

FEATURES = ['time_diff_minutes', 'distance_km', 'is_proxy_ip']

def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the distance between two points on Earth in kilometers.
    """
    R = 6371 # Earth's radius in km
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

    dlon = lon2 - lon1
    dlat = lat2 - lat1

    a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance = R * c
    return distance

def train_proxy_detector(data_for_training=None):
    global proxy_model
    if data_for_training is None or data_for_training.empty:
        print("No training data provided. Generating synthetic data for demo.")
        
        normal_data = {
            'time_diff_minutes': np.random.normal(2, 1, 90),
            'distance_km': np.random.normal(0.01, 0.005, 90),
            'is_proxy_ip': [0] * 90
        }
        
        anomalous_data = {
            'time_diff_minutes': np.random.normal(60, 15, 10),
            'distance_km': np.random.normal(500, 200, 10),
            'is_proxy_ip': [1] * 10
        }
        
        df_normal = pd.DataFrame(normal_data)
        df_anomalous = pd.DataFrame(anomalous_data)
        data_for_training = pd.concat([df_normal, df_anomalous]).sample(frac=1).reset_index(drop=True)

    print("Training Isolation Forest model...")
    proxy_model = IsolationForest(contamination=0.1, random_state=42)
    proxy_model.fit(data_for_training[FEATURES])
    
    joblib.dump(proxy_model, MODEL_PATH)
    print(f"Proxy detection model trained and saved to {MODEL_PATH}")

def load_proxy_detector_model():
    global proxy_model
    if proxy_model is None:
        if os.path.exists(MODEL_PATH):
            print(f"Loading proxy detection model from {MODEL_PATH}")
            proxy_model = joblib.load(MODEL_PATH)
        else:
            print("Proxy detection model not found. Training a dummy model with default data.")
            train_proxy_detector(None)
    return proxy_model

def detect_proxy(user_id, scan_timestamp, qr_gen_timestamp, user_lat, user_lon, qr_lat, qr_lon):
    model = load_proxy_detector_model()
    if model is None:
        print("ML model not loaded for proxy detection. Returning 'Legit' by default.")
        return 'Legit'
    
    try:
        scan_dt = datetime.fromisoformat(scan_timestamp)
        qr_gen_dt = datetime.fromisoformat(qr_gen_timestamp)
        time_diff_minutes = (scan_dt - qr_gen_dt).total_seconds() / 60
        
        distance_km = haversine_distance(user_lat, user_lon, qr_lat, qr_lon)
        
        is_proxy_ip = 1 if distance_km > 2 else 0

        input_features = pd.DataFrame([[time_diff_minutes, distance_km, is_proxy_ip]], columns=FEATURES)

        prediction = model.predict(input_features)[0]
        
        if prediction == -1:
            print(f"Anomaly detected for user {user_id}. Flagging as Suspicious.")
            return 'Suspicious'
        else:
            print(f"No anomaly detected for user {user_id}. Flagging as Legit.")
            return 'Legit'
    except Exception as e:
        print(f"Error during proxy detection prediction: {e}. Returning 'Legit'.")
        return 'Legit'

if __name__ == '__main__':
    train_proxy_detector(None)
    print("\n--- Testing Proxy Detection with Refined Logic ---")
    current_time = datetime.now()

    qr_gen_time_legit = (current_time - timedelta(minutes=2)).isoformat()
    legit_flag = detect_proxy("student_legit", current_time.isoformat(), qr_gen_time_legit, 19.317, 84.792, 19.317, 84.792)
    print(f"Legit case: {legit_flag}")

    qr_gen_time_old = (current_time - timedelta(hours=2)).isoformat()
    suspicious_flag_old = detect_proxy("student_old_qr", current_time.isoformat(), qr_gen_time_old, 19.317, 84.792, 20.279, 85.882)
    print(f"Suspicious (old QR) case: {suspicious_flag_old}")