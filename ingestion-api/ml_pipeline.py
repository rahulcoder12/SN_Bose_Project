import sqlite3
import joblib
import pandas as pd
pd.set_option('display.max_columns', None)  # Force pandas to show all columns
pd.set_option('display.width', 1000)        # Widen the display area
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import IsolationForest
import os

DB_FILE = "biometrics.db"

def extract_training_data():
    """
    Connects to the SQLite database and extracts all session profiles 
    into a Pandas DataFrame for Machine Learning.
    """
    if not os.path.exists(DB_FILE):
        print("❌ Error: Database file not found. Run the ingestion API first.")
        return None

    conn = sqlite3.connect(DB_FILE)
    
    # FIX: Added is_touch_device to the SELECT query
    query = """
        SELECT 
            session_id, 
            is_touch_device,
            total_keystrokes, 
            total_corrections, 
            running_error_rate, 
            total_mouse_distance_px, 
            total_scroll_distance_px
        FROM session_profiles
    """
    
    # Load directly into a Pandas DataFrame
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    if df.empty:
        print("⚠️ Warning: No session data found in the database.")
        return None
        
    return df

def normalize_features(df):
    """
    Scales numerical biometric features so they have a mean of 0 and variance of 1.
    This prevents large values (like mouse pixels) from dominating the ML model.
    """
    # 1. Separate the IDs from the actual math features
    features_to_scale = [
        "total_keystrokes", 
        "total_corrections", 
        "running_error_rate", 
        "total_mouse_distance_px", 
        "total_scroll_distance_px"
    ]
    
    # 2. Initialize the Scikit-Learn Scaler
    scaler = StandardScaler()
    
    # 3. Fit and transform the data
    df_scaled = df.copy()
    df_scaled[features_to_scale] = scaler.fit_transform(df[features_to_scale])
    
    return df_scaled, scaler

def train_anomaly_detector(df_scaled):
    """
    Trains an Isolation Forest model to detect abnormal user behavior.
    """
    # 1. Drop the session_id so the AI only looks at the math, not the strings
    X = df_scaled.drop(columns=["session_id"])
    
    # 2. Initialize the Isolation Forest
    # contamination=0.1 means we expect roughly 10% of sessions might be anomalies/intruders
    model = IsolationForest(n_estimators=100, contamination=0.1, random_state=42)
    
    # 3. Train the model on the biometric data
    model.fit(X)
    
    # 4. Generate predictions (-1 means Anomaly/Hacker, 1 means Normal User)
    predictions = model.predict(X)
    
    # 5. Get the raw anomaly score (lower negative numbers = higher risk)
    scores = model.decision_function(X)
    
    return model, predictions, scores

def train_all_models():
    """
    Automatically extracts the latest data, splits it by device, 
    and trains both AI models. Called by the background scheduler.
    """
    print("\n🔄 [CRON JOB] Starting Automated AI Retraining...")
    raw_data = extract_training_data()
    
    if raw_data is not None:
        # 1. Split the data
        df_desktop = raw_data[raw_data['is_touch_device'] == 0].copy()
        df_mobile = raw_data[raw_data['is_touch_device'] == 1].copy()
        
        # 2. Train Desktop
        if not df_desktop.empty:
            df_desktop = df_desktop.drop(columns=["is_touch_device"])
            scaled_desk, scaler_desk = normalize_features(df_desktop)
            model_desk, preds_desk, scores_desk = train_anomaly_detector(scaled_desk)
            joblib.dump(model_desk, "model_desktop.joblib")
            joblib.dump(scaler_desk, "scaler_desktop.joblib")
            print("   💾 [CRON] Desktop AI successfully updated.")
            
        # 3. Train Mobile
        if not df_mobile.empty:
            df_mobile = df_mobile.drop(columns=["is_touch_device"])
            scaled_mob, scaler_mob = normalize_features(df_mobile)
            model_mob, preds_mob, scores_mob = train_anomaly_detector(scaled_mob)
            joblib.dump(model_mob, "model_mobile.joblib")
            joblib.dump(scaler_mob, "scaler_mobile.joblib")
            print("   💾 [CRON] Mobile AI successfully updated.")

def train_user_baseline(session_id: str):
    """
    Enterprise Identity: Generates a personal biometric brain for a specific user.
    """
    conn = sqlite3.connect(DB_FILE)
    
    # Fetch only the calibration data for this exact session
    query = f"SELECT is_touch_device,keys_pressed, mistakes_made, error_rate, mouse_distance_px, scroll_distance_px FROM session_profiles WHERE session_id = '{session_id}'"
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    if df.empty:
        print(f"⚠️ No calibration data found for {session_id}")
        return False
        
    scaler = StandardScaler()
    scaled_features = scaler.fit_transform(df)
    
    # Contamination is extremely low (0.01) because this data is verified as safe
    model = IsolationForest(contamination=0.01, random_state=42)
    model.fit(scaled_features)
    
    # Save the personal brain directly to the hard drive
    joblib.dump(model, f"model_{session_id}.joblib")
    joblib.dump(scaler, f"scaler_{session_id}.joblib")
    
    print(f"✅ Personal baseline AI generated securely for {session_id}")
    return True

# Keep manual execution capability for testing
if __name__ == "__main__":
    train_all_models()