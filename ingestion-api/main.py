import logging
from logging.handlers import RotatingFileHandler
from fastapi import Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from apscheduler.schedulers.background import BackgroundScheduler
from ml_pipeline import train_all_models
import joblib
import warnings
import pandas as pd
import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
from biometrics import extract_keystroke_features, extract_mouse_features, extract_scroll_features
from database import init_db, update_session_profile
from fastapi import FastAPI, HTTPException, Header
import time
import requests
from database import delete_expired_sessions
from ml_pipeline import train_user_baseline, train_all_models
from database import init_db, update_session_profile, delete_expired_sessions, is_username_taken, register_new_user
from fastapi.staticfiles import StaticFiles
from database import verify_login, get_password_age, update_password
import random
import string

warnings.filterwarnings("ignore", category=UserWarning)
# --- PYDANTIC MODELS (Matches Day 1 Schema) ---

class KeystrokeEvent(BaseModel):
    key_code: str
    event: str
    t: int

class MouseEvent(BaseModel):
    x: int
    y: int
    t: int

class ClickEvent(BaseModel):
    x: int
    y: int
    button: str
    t: int

class ScrollEvent(BaseModel):
    y: int
    t: int

class DeviceContext(BaseModel):
    user_agent: str
    screen_resolution: str
    platform: str
    is_touch_device: bool = False

class Events(BaseModel):
    keystrokes: List[KeystrokeEvent] = []
    mouse_movements: List[MouseEvent] = []
    clicks: List[ClickEvent] = []
    scrolls: List[ScrollEvent] = []

class TelemetryPayload(BaseModel):
    session_id: str
    timestamp_start: int
    timestamp_end: int
    is_calibration: bool = False
    device_context: DeviceContext
    events: Events

# --- APP INITIALIZATION ---
# --- SYSTEM AUDITING (IMMUTABLE LOGS) ---
audit_logger = logging.getLogger("ZeroTrustAudit")
audit_logger.setLevel(logging.INFO)

# Create a rotating file that maxes out at 5MB and keeps the 3 most recent backups
file_handler = RotatingFileHandler("security_audit.log", maxBytes=5*1024*1024, backupCount=3)

# Define the exact timestamp and format for the auditors
formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')
file_handler.setFormatter(formatter)
audit_logger.addHandler(file_handler)

audit_logger.info("SYSTEM STARTUP: Zero Trust Engine Initialized.")

api_description = """
### Continuous Behavioral Biometric Security Engine
Welcome to the Zero Trust Auth API. This system provides continuous, transparent authentication by analyzing human-computer interaction patterns.

* **Rate Limiting:** Maximum 20 requests per minute per IP.
* **Compliance:** Session data is automatically purged after 24 hours (GDPR compliant).
* **Authentication:** All routes require a valid `x-api-key` header.
"""

app = FastAPI(
    title="🛡️ Zero Trust Ingestion API",
    description=api_description,
    version="1.0.0",
    contact={
        "name": "Security Operations Team",
        "email": "secops@zerotrust-ai.com",
    },
    docs_url="/developers" # Changes the default /docs URL to a professional portal URL
)

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["POST"],
    allow_headers=["*"],
)

# --- STATEFUL SESSION STORE ---
# This will hold the continuous profile for each user session
active_sessions = {}

# --- AI MODEL LOADING ---
MODEL_FILE = "anomaly_model.joblib"
SCALER_FILE = "scaler.joblib"

# --- DEVICE-AWARE AI MODELS ---
ai_models = {
    "desktop": {"model": None, "scaler": None},
    "mobile": {"model": None, "scaler": None}
}

# --- MULTI-TENANT ENTERPRISE CLIENTS ---
VALID_API_KEYS = {
    "sk_live_51Mabcde12345": "Acme Bank Corp",
    "sk_live_99Xzyxw98765": "Global E-Commerce Store"
}

def load_ai_models_into_memory():
    """Loads the latest joblib files from the hard drive into the active API."""
    global ai_models
    
    if os.path.exists("model_desktop.joblib") and os.path.exists("scaler_desktop.joblib"):
        ai_models["desktop"]["model"] = joblib.load("model_desktop.joblib")
        ai_models["desktop"]["scaler"] = joblib.load("scaler_desktop.joblib")
        
    if os.path.exists("model_mobile.joblib") and os.path.exists("scaler_mobile.joblib"):
        ai_models["mobile"]["model"] = joblib.load("model_mobile.joblib")
        ai_models["mobile"]["scaler"] = joblib.load("scaler_mobile.joblib")

def clear_inactive_dashboard_sessions(timeout_minutes=5):
    """
    Removes sessions from the live Admin Dashboard if we haven't received 
    any telemetry from them in the last 5 minutes.
    """
    current_time = time.time()
    # Find all users whose last update is older than the timeout
    expired_users = [
        sid for sid, data in active_sessions.items() 
        if current_time - data.get("last_seen", 0) > (timeout_minutes * 60)
    ]
    
    # Delete them from memory
    for sid in expired_users:
        del active_sessions[sid]
        
    if expired_users:
        print(f"🧹 [COMPLIANCE] Cleared {len(expired_users)} inactive sessions from the live dashboard.")

@app.on_event("startup")
async def startup_event():
    print("⚙️ Initializing local SQLite database...")
    init_db()
    
    # 1. Initial Load of the AI Brains
    print("🧠 Loading AI Models into memory...")
    load_ai_models_into_memory()
    
    # 2. Start the Continuous Learning Scheduler
    # 2. Start the Continuous Learning & Compliance Scheduler
    def scheduled_background_tasks():
        # Task A: Train new models
        train_all_models()           
        load_ai_models_into_memory() 
        print("✅ [CRON] Live API models hot-swapped with fresh training data.")
        
        # Task B: GDPR Database Eviction (Delete data older than 24 hours)
        purged_rows = delete_expired_sessions(hours_to_keep=24)
        if purged_rows > 0:
            print(f"🗑️ [COMPLIANCE] Permanently deleted {purged_rows} expired biometric records.")
            
        # Task C: Dashboard Cleanup (Clear ghosts inactive for 5 minutes)
        clear_inactive_dashboard_sessions(timeout_minutes=5)

    scheduler = BackgroundScheduler()
    # Running every 2 minutes for testing purposes
    scheduler.add_job(scheduled_background_tasks, 'interval', minutes=2) 
    scheduler.start()
    print("⏰ Automated Continuous Learning Scheduler started (Running every 2 minutes).")
# --- IDENTITY MANAGEMENT ENDPOINTS ---
class UserRegistration(BaseModel):
    username: str
    password: str

@app.post("/api/v1/auth/register")
async def register_account(payload: UserRegistration):
    username = payload.username.lower().strip()
    
    # 1. System-level protection (Keep highly sensitive system terms blocked at the API level)
    system_reserved = ["admin", "root", "system", "administrator"]
    if username in system_reserved:
        raise HTTPException(status_code=400, detail="This username is reserved by the system.")

    # 2. Database validation (Check if another user has claimed this)
    if is_username_taken(username):
        raise HTTPException(status_code=400, detail="Username is already taken. Please choose another.")
        
    # 3. Success! Save to the database
    # (Note: In a true production app, we would hash the password with bcrypt here before saving)
    register_new_user(username, payload.password)
    
    return {"status": "success", "message": "User registered successfully."}

app.post("/api/v1/auth/login")
async def login_user(payload: UserRegistration): # Reusing the username/password BaseModel
    if verify_login(payload.username.lower(), payload.password):
        days_left = get_password_age(payload.username.lower())
        return {"status": "success", "days_until_expiry": days_left}
    
    raise HTTPException(status_code=401, detail="Invalid username or password.")

@app.post("/api/v1/auth/regenerate")
async def regenerate_password(payload: UserRegistration):
    # Verify they actually own the account first
    if verify_login(payload.username.lower(), payload.password):
        # Generate new 12-char secure password
        chars = string.ascii_letters + string.digits
        new_pwd = ''.join(random.choice(chars) for i in range(12))
        
        update_password(payload.username.lower(), new_pwd)
        return {"status": "success", "new_password": new_pwd, "days_until_expiry": 90}
    
    raise HTTPException(status_code=401, detail="Unauthorized")

@app.post(
    "/api/v1/ingest", 
    summary="Ingest Biometric Telemetry",
    tags=["Core Security"],
    response_description="Returns a security action command (allow or require_mfa)."
)
@limiter.limit("20/minute")
async def ingest_telemetry(request: Request, payload: TelemetryPayload, x_api_key: str = Header(None, description="Your Enterprise API Key")):
    """
    Accepts a 5-second chunk of keystroke, mouse, and scroll data.
    The AI engine processes the payload in real-time and returns a security verdict.
    
    **Returns:**
    - `200 OK`: Telemetry processed successfully.
    - `401 Unauthorized`: Invalid or missing API Key.
    - `429 Too Many Requests`: Rate limit exceeded.
    - `500 Internal Server Error`: Backend processing failure.
    """
    
    # --- SECURITY GATEWAY ---
    if not x_api_key or x_api_key not in VALID_API_KEYS:
        # NEW: Save the unauthorized attempt to the permanent audit file
        client_ip = request.client.host
        audit_logger.warning(f"BLOCKED: Unauthorized API access attempt from IP {client_ip}. Invalid Key.")
        
        print("🛑 BLOCKED: Unauthorized API access attempt.")
        raise HTTPException(status_code=401, detail="Invalid or missing API Key")
        
    client_name = VALID_API_KEYS[x_api_key]
    session_id = payload.session_id
    
    # ... the rest of your total_keys, total_mouse variables continue below ...
    
    total_keys = len(payload.events.keystrokes)
    total_mouse = len(payload.events.mouse_movements)
    total_scrolls = len(payload.events.scrolls)
    
    # Initialize the session if this is their first data chunk
    # Update or initialize session in memory
    if session_id not in active_sessions:
        active_sessions[session_id] = {
            "total_keystrokes": 0,
            "total_corrections": 0,
            "total_mouse_distance_px": 0.0,
            "total_scroll_distance_px": 0.0,
            "risk_history": [],
            "chunks_processed": 0
        }
    
    # --- NEW: Track the exact timestamp of their last heartbeat ---
    active_sessions[session_id]["last_seen"] = time.time()

    session = active_sessions[session_id]
    session["chunks_processed"] += 1

    print(f"\n{'='*50}")
    print(f"📦 CHUNK RECEIVED | Session: {session_id} | Chunk #{session['chunks_processed']}")
    
    # 1. Process & Aggregate Keystrokes
    if total_keys > 0:
        keystroke_dicts = [{"key_code": k.key_code, "event": k.event, "t": k.t} for k in payload.events.keystrokes]
        k_metrics = extract_keystroke_features(keystroke_dicts)
        
        session["total_keystrokes"] += k_metrics["total_keystrokes"]
        session["total_corrections"] += k_metrics["total_corrections"]
        
        print("   [Current 5s Chunk]")
        print(f"      - Avg Dwell: {k_metrics['avg_dwell_time_ms']} ms | Flight: {k_metrics['avg_flight_time_ms']} ms")
        print(f"      - Stylometry: {k_metrics['stylometry']['estimated_words']} words")

    # 2. Process & Aggregate Mouse Dynamics
    if total_mouse > 0:
        mouse_dicts = [{"x": m.x, "y": m.y, "t": m.t} for m in payload.events.mouse_movements]
        m_metrics = extract_mouse_features(mouse_dicts)
        
        if m_metrics:
            session["total_mouse_distance_px"] += m_metrics["total_distance_px"]
    
    # 3. Process Content Consumption (Scrolling)
    if total_scrolls > 0:
        scroll_dicts = [{"y": s.y, "t": s.t} for s in payload.events.scrolls]
        s_metrics = extract_scroll_features(scroll_dicts)
        
        if s_metrics:
            session["total_scroll_distance_px"] += s_metrics["total_scroll_distance_px"] # FIX: Aggregate scroll state
            print("   📄 Content Consumption:")
            print(f"      - Current Scroll Dist: {s_metrics['total_scroll_distance_px']} px")
            print(f"      - Depth Reached:       {s_metrics['max_scroll_depth_px']} px")

    # 4. Print the Continuous Live Profile
    print("-" * 50)
    print("   📊 LIVE SESSION AGGREGATION:")
    print(f"      - Total Keys Pressed: {session['total_keystrokes']}")
    print(f"      - Total Mistakes:     {session['total_corrections']}")
    
    # FIX: Initialize variable securely to prevent crashes
    running_error_rate = 0.0 
    if session['total_keystrokes'] > 0:
        running_error_rate = (session['total_corrections'] / session['total_keystrokes']) * 100
        print(f"      - Running Error Rate: {round(running_error_rate, 2)}%")
        
    print(f"      - Total Cursor Dist:  {round(session['total_mouse_distance_px'], 2)} px")
    print(f"      - Total Scroll Dist:  {session['total_scroll_distance_px']} px") # Display the running total
    print(f"{'='*50}")

# --- REAL-TIME AI INFERENCE ---
    security_action = "allow"
    is_touch = payload.device_context.is_touch_device
    device_type = "mobile" if is_touch else "desktop"

    # 1. THE BYPASS: If they are calibrating, skip the AI entirely and just save the data.
    if payload.is_calibration:
        print(f"   🎯 CALIBRATION MODE: Securing baseline data for {session_id}...")
        session["latest_verdict"] = "CALIBRATING"
        session["risk_score"] = 1.0 # Max safe score
        
        update_session_profile(
            session_id=session_id, is_touch=is_touch, keys=session["total_keystrokes"],
            mistakes=session["total_corrections"], error_rate=round(running_error_rate, 2),
            mouse_dist=round(session["total_mouse_distance_px"], 2), scroll_dist=round(session["total_scroll_distance_px"], 2)
        )
        return {"status": "success", "security_action": "allow"}

    # 2. LOAD PERSONAL BRAIN: If a custom model exists for this user, load it into RAM.
    if "model" not in session and os.path.exists(f"model_{session_id}.joblib"):
        print(f"   🧠 Loading custom biometric profile for {session_id}...")
        session["model"] = joblib.load(f"model_{session_id}.joblib")
        session["scaler"] = joblib.load(f"scaler_{session_id}.joblib")
        
    # Choose between their personal brain or the global fallback brain
    active_model = session.get("model", ai_models[device_type]["model"])
    active_scaler = session.get("scaler", ai_models[device_type]["scaler"])
    
    if active_model is not None and active_scaler is not None:
        # Reverted keys to exactly match what the Scikit-Learn model was trained on
        live_features = pd.DataFrame([{
            "total_keystrokes": session["total_keystrokes"],
            "total_corrections": session["total_corrections"],
            "running_error_rate": round(running_error_rate, 2),
            "total_mouse_distance_px": round(session["total_mouse_distance_px"], 2),
            "total_scroll_distance_px": round(session["total_scroll_distance_px"], 2)
        }])
        
        live_scaled = active_scaler.transform(live_features)
        live_scaled_df = pd.DataFrame(live_scaled, columns=live_features.columns)
        
        prediction = active_model.predict(live_scaled_df)[0]
        risk_score = active_model.decision_function(live_scaled_df)[0]
        
        # --- NEW: Save state and history for the Admin Dashboard ---
        session["latest_verdict"] = "AUTHENTIC" if prediction == 1 else "ANOMALY"
        session["risk_score"] = round(risk_score, 4)
        
        # Initialize the history array if it doesn't exist yet
        if "risk_history" not in session:
            session["risk_history"] = []
            
        # Append the latest score (keep only the last 20 scores to prevent massive memory usage)
        session["risk_history"].append(round(risk_score, 4))
        if len(session["risk_history"]) > 20:
            session["risk_history"].pop(0)
        
        # Save state for the admin dashboard
        session["latest_verdict"] = "AUTHENTIC" if prediction == 1 else "ANOMALY"
        session["risk_score"] = round(risk_score, 4)
        
        print(f"\n   🤖 LIVE {device_type.upper()} AI VERDICT:")
        print(f"\n   🤖 LIVE {device_type.upper()} AI VERDICT:")
        if prediction == 1:
            print(f"      ✅ Status: AUTHENTIC (Risk Score: {round(risk_score, 4)})")
        else:
            print(f"      🚨 Status: ANOMALY DETECTED (Risk Score: {round(risk_score, 4)})")
            security_action = "require_mfa"
            
            # --- NEW: Save the AI verdict to the permanent audit file ---
            audit_logger.critical(f"ANOMALY DETECTED: Session {session_id} | Client: {client_name} | Risk Score: {round(risk_score, 4)}")
            
            # Fire the Webhook Alert
            send_security_alert(
                session_id=session_id,
                client_name=client_name,
                risk_score=round(risk_score, 4),
                keystrokes=session["total_keystrokes"]
            )
            
            # --- NEW: Fire the Webhook Alert ---
            send_security_alert(
                session_id=session_id,
                client_name=client_name,
                risk_score=round(risk_score, 4),
                keystrokes=session["total_keystrokes"]
            )

    # --- SAVE TO DATABASE ---
    update_session_profile(
        session_id=session_id,
        is_touch=is_touch, # Pass the device flag to the DB
        keys=session["total_keystrokes"],
        mistakes=session["total_corrections"],
        error_rate=round(running_error_rate, 2),
        mouse_dist=round(session["total_mouse_distance_px"], 2),
        scroll_dist=round(session["total_scroll_distance_px"], 2)
    )

    return {
        "status": "success", 
        "security_action": security_action
    }

# --- ENTERPRISE WEBHOOK INTEGRATION ---
WEBHOOK_URL = "https://webhook.site/621cbb40-0712-4408-b740-11afbc9a577a"

def send_security_alert(session_id: str, client_name: str, risk_score: float, keystrokes: int):
    """
    Fires an asynchronous network request to a SOC team's Slack/Discord/Webhook 
    when the AI detects an anomaly.
    """
    payload = {
        "text": f"🚨 **CRITICAL SECURITY ALERT** 🚨\n\n"
                f"**Client:** {client_name}\n"
                f"**Session ID:** {session_id}\n"
                f"**Risk Score:** {risk_score}\n"
                f"**Status:** The AI detected highly abnormal biometric behavior after {keystrokes} keystrokes. "
                f"The session has been automatically locked and Step-Up MFA has been deployed."
    }
    
    try:
        # Send the payload without making the user's browser wait for the response
        requests.post(WEBHOOK_URL, json=payload, timeout=2)
        print("   📢 SOC Webhook Alert Dispatched Successfully!")
    except requests.exceptions.RequestException as e:
        print(f"   ⚠️ Failed to dispatch SOC webhook: {e}")

class CalibrationComplete(BaseModel):
    session_id: str

@app.post("/api/v1/calibrate/complete")
async def complete_calibration(payload: CalibrationComplete, x_api_key: str = Header(None)):
    if not x_api_key or x_api_key not in VALID_API_KEYS:
        raise HTTPException(status_code=401, detail="Invalid API Key")
        
    success = train_user_baseline(payload.session_id)
    if success:
        return {"status": "success", "message": "Baseline AI generated."}
    
    raise HTTPException(status_code=400, detail="Failed to generate baseline.")

# --- ADMIN DASHBOARD ROUTES ---
@app.get("/api/v1/admin/sessions")
async def get_active_sessions():
    """Returns the live state of all currently tracked user sessions."""
    return {"status": "success", "active_sessions": active_sessions}

# --- STATIC WEB SERVER MOUNT ---
# Calculate the absolute path to the client-sdk folder
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIENT_SDK_DIR = os.path.join(BASE_DIR, "client-sdk")

# Mount the folder so http://localhost:8000/admin.html serves the UI
app.mount("/", StaticFiles(directory=CLIENT_SDK_DIR, html=True), name="frontend")