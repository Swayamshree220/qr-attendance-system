# qr_attendance/app/ml_model/reliability_predictor.py
import pandas as pd
from sklearn.linear_model import LogisticRegression # Or other classification models
import joblib
import os

reliability_model = None
MODEL_PATH = os.path.join(os.path.dirname(__file__), 'reliability_model.pkl')

def train_reliability_predictor(attendance_history_df):
    """
    Trains and saves a model to predict student reliability.
    Input: DataFrame of historical attendance data.
    Features could be: average attendance, recent attendance, etc.
    Target: Is student likely to miss next class? (0/1)
    """
    global reliability_model
    if attendance_history_df is None or attendance_history_df.empty:
        # Create dummy data for initial training
        data = {
            'student_id': ['s1', 's1', 's1', 's2', 's2', 's3', 's3', 's3', 's3'],
            'session_id': [f'sess{i}' for i in range(9)],
            'is_present': [1, 1, 0, 1, 0, 1, 1, 1, 0], # 1 = present, 0 = absent
            'session_date': pd.to_datetime(['2025-07-01', '2025-07-02', '2025-07-03',
                                            '2025-07-01', '2025-07-02', '2025-07-01',
                                            '2025-07-02', '2025-07-03', '2025-07-04'])
        }
        attendance_history_df = pd.DataFrame(data)

    print("Training Reliability Predictor model...")

    # Feature engineering for reliability:
    # Example: Calculate rolling average attendance
    # This requires more sophisticated data aggregation, for now, a simplified approach
    # For a real model, `attendance_history_df` should be grouped by student_id
    # and features like 'last_5_attendance_rate', 'total_absences', 'streaks' derived.
    # For this placeholder, we'll just train a dummy model.

    # Dummy features (replace with actual engineered features)
    features = ['dummy_feature']
    attendance_history_df['dummy_feature'] = attendance_history_df['is_present'] # Just for training

    # Dummy target: For demonstration, let's say a student is "unreliable" (0) if they missed the last class.
    # In reality, this would be based on future attendance.
    attendance_history_df['is_unreliable'] = attendance_history_df['is_present'].shift(-1).fillna(1) # Predict if next is a miss

    # Filter out rows where target is NaN (last entry for each student)
    train_df = attendance_history_df.dropna()

    if train_df.empty:
        print("Not enough data to train reliability model.")
        reliability_model = None
        return

    reliability_model = LogisticRegression(random_state=42)
    # Ensure 'dummy_feature' exists if training with dummy data
    if 'dummy_feature' not in train_df.columns:
        train_df['dummy_feature'] = 0 # Placeholder if column not created correctly

    # Reshape if only one feature
    X_train = train_df[['dummy_feature']] # Or actual engineered features
    y_train = train_df['is_unreliable']

    reliability_model.fit(X_train, y_train)
    joblib.dump(reliability_model, MODEL_PATH)
    print(f"Reliability model trained and saved to {MODEL_PATH}")

def load_reliability_predictor_model():
    """Loads the trained reliability model."""
    global reliability_model
    if reliability_model is None and os.path.exists(MODEL_PATH):
        print(f"Loading reliability predictor model from {MODEL_PATH}")
        reliability_model = joblib.load(MODEL_PATH)
    elif reliability_model is None:
        print("Reliability predictor model not found. Training a dummy model.")
        train_reliability_predictor(None) # Train with dummy data if not found
    return reliability_model


def predict_reliability(student_id, student_attendance_history_df):
    """
    Predicts reliability score for a given student.
    Input: student_id and their historical attendance DataFrame.
    Output: reliability score (0-100%)
    """
    model = load_reliability_predictor_model()
    if model is None:
        print("ML reliability model not loaded. Returning default reliability.")
        return 75.0 # Default reliability if model not ready

    # Feature engineering for prediction (must match training)
    # This needs to be done based on `student_attendance_history_df`
    # For initial setup, we'll use a simple placeholder
    # Example: last attendance status as a feature (0 or 1)
    if student_attendance_history_df is None or student_attendance_history_df.empty:
        features_for_prediction = pd.DataFrame([[1]], columns=['dummy_feature']) # Assume present if no history
    else:
        last_attendance = student_attendance_history_df.sort_values('timestamp', ascending=False).iloc[0]['is_present']
        features_for_prediction = pd.DataFrame([[last_attendance]], columns=['dummy_feature'])


    # Ensure the feature column exists
    if 'dummy_feature' not in features_for_prediction.columns:
        features_for_prediction['dummy_feature'] = 0 # Fallback

    # Predict probability of being unreliable (e.g., probability of target being 0)
    # Adjust based on your model's target definition
    if hasattr(model, 'predict_proba'):
        # Predict probability of class 0 (unreliable)
        # Assuming 0 means unreliable, 1 means reliable
        probability_unreliable = model.predict_proba(features_for_prediction)[:, 0][0]
        reliability_score = (1 - probability_unreliable) * 100
    else:
        # Fallback if model doesn't have predict_proba (e.g., IsolationForest)
        # You'd need a different interpretation or a different model for scores
        reliability_score = 75.0 # Default if score not directly available

    return round(reliability_score, 2)


# For testing the ML part independently
if __name__ == '__main__':
    # Prepare some dummy attendance history for testing
    from datetime import datetime, timedelta
    dummy_history = []
    for i in range(10):
        dummy_history.append({
            'student_id': 'test_student',
            'session_id': f'sess_{i}',
            'is_present': 1 if i % 3 != 0 else 0, # Present, Absent, Present, Present, Absent...
            'timestamp': datetime.now() - timedelta(days=9-i),
            'scanned_latitude': 19.82,
            'scanned_longitude': 85.82,
            'ml_proxy_flag': 'Legit',
            'ml_reliability_score': None,
            'face_verified': True
        })
    dummy_df = pd.DataFrame(dummy_history)

    # Train a model if it doesn't exist
    train_reliability_predictor(dummy_df)

    # Test prediction
    print("\n--- Testing Reliability Prediction ---")
    reliability = predict_reliability('test_student', dummy_df)
    print(f"Test student reliability: {reliability:.2f}%")

    # Another student with bad history
    bad_history = []
    for i in range(5):
        bad_history.append({
            'student_id': 'unreliable_student',
            'session_id': f'bsess_{i}',
            'is_present': 0 if i % 2 == 0 else 1, # Absent, Present, Absent, Present, Absent
            'timestamp': datetime.now() - timedelta(days=4-i),
            'scanned_latitude': 19.82,
            'scanned_longitude': 85.82,
            'ml_proxy_flag': 'Legit',
            'ml_reliability_score': None,
            'face_verified': True
        })
    bad_df = pd.DataFrame(bad_history)

    bad_reliability = predict_reliability('unreliable_student', bad_df)
    print(f"Unreliable student reliability: {bad_reliability:.2f}%")