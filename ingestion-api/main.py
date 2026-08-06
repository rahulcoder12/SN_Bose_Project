"""
🛡️ Zero Trust Ingestion API — Continuous Behavioral Biometric Security Engine
Main application module: routes, middleware, scheduling, and AI inference.
"""

# --- CLEAN IMPORTS ---
import os
import re
import time
import string
import secrets
import logging
import warnings
import traceback
from logging.handlers import RotatingFileHandler
from typing import List

import joblib
import pandas as pd
import requests
from fastapi import FastAPI, HTTPException, Request, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from apscheduler.schedulers.background import BackgroundScheduler
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.gzip import GZipMiddleware

from auth import (
    create_access_token, create_refresh_token, verify_token,
    get_current_user, verify_api_key, VALID_API_KEYS
)
from biometrics import extract_keystroke_features, extract_mouse_features, extract_scroll_features
from database import (
    init_db, init_pool, update_session_profile, delete_expired_sessions,
    is_username_taken, register_new_user, verify_login, get_password_age, update_password
)
from ml_pipeline import train_user_baseline, train_all_models

warnings.filterwarnings("ignore", category=UserWarning)


# --- PYDANTIC MODELS ---
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
    session_id: str = Field(min_length=1, max_length=128)
    timestamp_start: int
    timestamp_end: int
    is_calibration: bool = False
    device_context: DeviceContext
    events: Events

class UserRegistration(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=8, max_length=128)
    
    @field_validator('username')
    @classmethod
    def validate_username(cls, v):
        v = v.lower().strip()
        if not re.match(r'^[a-z0-9_]+$', v):
            raise ValueError('Username can only contain lowercase letters, numbers, and underscores')
        reserved = ["admin", "root", "system", "administrator", "superuser", "mod"]
        if v in reserved:
            raise ValueError('This username is reserved by the system')
        return v

class LoginRequest(BaseModel):
    """Separate model for login — different validation rules than registration."""
    username: str = Field(min_length=1, max_length=32)
    password: str = Field(min_length=1, max_length=128)

class CalibrationComplete(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)

class TokenRefresh(BaseModel):
    refresh_token: str


# --- SYSTEM AUDITING (IMMUTABLE LOGS) ---
audit_logger = logging.getLogger("ZeroTrustAudit")
audit_logger.setLevel(logging.INFO)

file_handler = RotatingFileHandler("security_audit.log", maxBytes=5*1024*1024, backupCount=3)
formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')
file_handler.setFormatter(formatter)
audit_logger.addHandler(file_handler)

audit_logger.info("SYSTEM STARTUP: Zero Trust Engine Initialized.")


# --- APP INITIALIZATION ---
api_description = """
### Continuous Behavioral Biometric Security Engine
Welcome to the Zero Trust Auth API. This system provides continuous, transparent authentication by analyzing human-computer interaction patterns.

* **Rate Limiting:** Maximum 20 requests per minute per IP.
* **Compliance:** Session data is automatically purged after 24 hours (GDPR compliant).
* **Authentication:** Telemetry routes require a valid `x-api-key` header. Management routes require a JWT Bearer token.
"""

app = FastAPI(
    title="🛡️ Zero Trust Ingestion API",
    description=api_description,
    version="2.0.0",
    contact={
        "name": "Security Operations Team",
        "email": "secops@zerotrust-ai.com",
    },
    docs_url="/developers"
)

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# --- SECURITY HEADERS MIDDLEWARE ---
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=1000)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# --- GLOBAL EXCEPTION HANDLERS ---
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catches any unhandled exception and returns a clean JSON error."""
    audit_logger.error(f"UNHANDLED ERROR: {request.method} {request.url.path} | {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"status": "error", "detail": "An internal server error occurred. Please try again later."}
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Standardizes all HTTP error responses."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"status": "error", "detail": exc.detail}
    )


# --- STATEFUL SESSION STORE ---
active_sessions = {}

# --- DEVICE-AWARE AI MODELS ---
ai_models = {
    "desktop": {"model": None, "scaler": None},
    "mobile": {"model": None, "scaler": None}
}

# --- WEBHOOK URL (from env) ---
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")


def load_ai_models_into_memory():
    """Loads the latest joblib files from disk into the active API."""
    global ai_models
    
    if os.path.exists("model_desktop.joblib") and os.path.exists("scaler_desktop.joblib"):
        ai_models["desktop"]["model"] = joblib.load("model_desktop.joblib")
        ai_models["desktop"]["scaler"] = joblib.load("scaler_desktop.joblib")
        
    if os.path.exists("model_mobile.joblib") and os.path.exists("scaler_mobile.joblib"):
        ai_models["mobile"]["model"] = joblib.load("model_mobile.joblib")
        ai_models["mobile"]["scaler"] = joblib.load("scaler_mobile.joblib")


def clear_inactive_dashboard_sessions(timeout_minutes=5):
    """Removes sessions from the live dashboard if inactive for the specified timeout."""
    current_time = time.time()
    expired_users = [
        sid for sid, data in list(active_sessions.items())
        if current_time - data.get("last_seen", 0) > (timeout_minutes * 60)
    ]
    
    for sid in expired_users:
        del active_sessions[sid]
        
    if expired_users:
        print(f"🧹 [COMPLIANCE] Cleared {len(expired_users)} inactive sessions from the live dashboard.")


# --- STARTUP EVENT ---
@app.on_event("startup")
async def startup_event():
    print("⚙️ Initializing database connection pool...")
    init_pool()
    
    print("⚙️ Initializing database tables...")
    init_db()
    
    print("🧠 Loading AI Models into memory...")
    load_ai_models_into_memory()
    
    # Background scheduler for continuous learning & compliance
    def scheduled_background_tasks():
        # Task A: Train new models from latest data
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
    scheduler.add_job(scheduled_background_tasks, 'interval', minutes=2) 
    scheduler.start()
    print("⏰ Automated Continuous Learning Scheduler started (Running every 2 minutes).")


# ========================================================================
#                     IDENTITY MANAGEMENT ENDPOINTS
# ========================================================================

@app.post("/api/v1/auth/register", tags=["Authentication"])
@limiter.limit("3/minute")
async def register_account(request: Request, payload: UserRegistration):
    """Register a new user account with a username and password."""
    username = payload.username  # Already cleaned by Pydantic validator

    if is_username_taken(username):
        raise HTTPException(status_code=400, detail="Username is already taken. Please choose another.")
        
    register_new_user(username, payload.password)
    audit_logger.info(f"USER REGISTERED: {username}")
    
    return {"status": "success", "message": "User registered successfully."}


@app.post("/api/v1/auth/login", tags=["Authentication"])
@limiter.limit("5/minute")
async def login_user(request: Request, payload: LoginRequest):
    """Authenticate with username/password and receive JWT access + refresh tokens."""
    username = payload.username.lower().strip()
    
    if not verify_login(username, payload.password):
        audit_logger.warning(f"FAILED LOGIN: Attempt for user '{username}' from IP {request.client.host}")
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    
    days_left = get_password_age(username)
    
    access_token = create_access_token(data={"sub": username})
    refresh_token = create_refresh_token(data={"sub": username})
    
    audit_logger.info(f"USER LOGIN: {username} from IP {request.client.host}")
    
    return {
        "status": "success",
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "days_until_expiry": days_left
    }


@app.post("/api/v1/auth/refresh", tags=["Authentication"])
async def refresh_access_token(payload: TokenRefresh):
    """Issue a new access token using a valid refresh token."""
    token_data = verify_token(payload.refresh_token, expected_type="refresh")
    username = token_data.get("sub")
    
    new_access_token = create_access_token(data={"sub": username})
    return {
        "status": "success",
        "access_token": new_access_token,
        "token_type": "bearer"
    }


@app.get("/api/v1/auth/me", tags=["Authentication"])
async def get_my_profile(current_user: str = Depends(get_current_user)):
    """Returns the profile of the currently authenticated user."""
    days_left = get_password_age(current_user)
    return {
        "status": "success",
        "username": current_user,
        "days_until_expiry": days_left
    }


@app.post("/api/v1/auth/regenerate", tags=["Authentication"])
async def regenerate_password(current_user: str = Depends(get_current_user)):
    """Regenerates the password for the currently authenticated user. Requires JWT Bearer token."""
    chars = string.ascii_letters + string.digits
    new_pwd = ''.join(secrets.choice(chars) for _ in range(16))
    
    update_password(current_user, new_pwd)
    audit_logger.info(f"PASSWORD ROTATED: User '{current_user}' regenerated their password.")
    
    return {"status": "success", "new_password": new_pwd, "days_until_expiry": 90}


# ========================================================================
#                     CORE TELEMETRY INGESTION
# ========================================================================

@app.post(
    "/api/v1/ingest", 
    summary="Ingest Biometric Telemetry",
    tags=["Core Security"],
    response_description="Returns a security action command (allow or require_mfa)."
)
@limiter.limit("20/minute")
async def ingest_telemetry(
    request: Request, 
    payload: TelemetryPayload, 
    client_name: str = Depends(verify_api_key)
):
    """
    Accepts a 5-second chunk of keystroke, mouse, and scroll data.
    The AI engine processes the payload in real-time and returns a security verdict.
    
    **Returns:**
    - `200 OK`: Telemetry processed successfully.
    - `401 Unauthorized`: Invalid or missing API Key.
    - `429 Too Many Requests`: Rate limit exceeded.
    - `500 Internal Server Error`: Backend processing failure.
    """
    session_id = payload.session_id
    
    total_keys = len(payload.events.keystrokes)
    total_mouse = len(payload.events.mouse_movements)
    total_scrolls = len(payload.events.scrolls)
    
    # Initialize or update session in memory
    if session_id not in active_sessions:
        active_sessions[session_id] = {
            "total_keystrokes": 0,
            "total_corrections": 0,
            "total_mouse_distance_px": 0.0,
            "total_scroll_distance_px": 0.0,
            "risk_history": [],
            "chunks_processed": 0
        }
    
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
            session["total_scroll_distance_px"] += s_metrics["total_scroll_distance_px"]
            print("   📄 Content Consumption:")
            print(f"      - Current Scroll Dist: {s_metrics['total_scroll_distance_px']} px")
            print(f"      - Depth Reached:       {s_metrics['max_scroll_depth_px']} px")

    # 4. Compute running error rate
    running_error_rate = 0.0 
    if session['total_keystrokes'] > 0:
        running_error_rate = (session['total_corrections'] / session['total_keystrokes']) * 100

    print("-" * 50)
    print("   📊 LIVE SESSION AGGREGATION:")
    print(f"      - Total Keys Pressed: {session['total_keystrokes']}")
    print(f"      - Total Mistakes:     {session['total_corrections']}")
    if session['total_keystrokes'] > 0:
        print(f"      - Running Error Rate: {round(running_error_rate, 2)}%")
    print(f"      - Total Cursor Dist:  {round(session['total_mouse_distance_px'], 2)} px")
    print(f"      - Total Scroll Dist:  {session['total_scroll_distance_px']} px")
    print(f"{'='*50}")

    # --- REAL-TIME AI INFERENCE ---
    security_action = "allow"
    is_touch = payload.device_context.is_touch_device
    device_type = "mobile" if is_touch else "desktop"

    # Calibration bypass — just save data, no AI verdict
    if payload.is_calibration:
        print(f"   🎯 CALIBRATION MODE: Securing baseline data for {session_id}...")
        session["latest_verdict"] = "CALIBRATING"
        session["risk_score"] = 1.0
        
        update_session_profile(
            session_id=session_id, is_touch=is_touch, keys=session["total_keystrokes"],
            mistakes=session["total_corrections"], error_rate=round(running_error_rate, 2),
            mouse_dist=round(session["total_mouse_distance_px"], 2), 
            scroll_dist=round(session["total_scroll_distance_px"], 2)
        )
        return {"status": "success", "security_action": "allow"}

    # Load personal model if available
    if "model" not in session and os.path.exists(f"model_{session_id}.joblib"):
        print(f"   🧠 Loading custom biometric profile for {session_id}...")
        session["model"] = joblib.load(f"model_{session_id}.joblib")
        session["scaler"] = joblib.load(f"scaler_{session_id}.joblib")
        
    # Choose between personal brain or global fallback
    active_model = session.get("model", ai_models[device_type]["model"])
    active_scaler = session.get("scaler", ai_models[device_type]["scaler"])
    
    if active_model is not None and active_scaler is not None:
        try:
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
            
            # Save state for admin dashboard
            session["latest_verdict"] = "AUTHENTIC" if prediction == 1 else "ANOMALY"
            session["risk_score"] = round(risk_score, 4)
            
            # Track risk history (keep last 20 scores)
            if "risk_history" not in session:
                session["risk_history"] = []
            session["risk_history"].append(round(risk_score, 4))
            if len(session["risk_history"]) > 20:
                session["risk_history"].pop(0)
            
            print(f"\n   🤖 LIVE {device_type.upper()} AI VERDICT:")
            if prediction == 1:
                print(f"      ✅ Status: AUTHENTIC (Risk Score: {round(risk_score, 4)})")
            else:
                print(f"      🚨 Status: ANOMALY DETECTED (Risk Score: {round(risk_score, 4)})")
                
                # Check for 2-minute cool down on alerts
                current_time = time.time()
                last_alert = session.get("last_alert_time", 0)
                
                if current_time - last_alert >= 120:
                    security_action = "require_mfa"
                    session["last_alert_time"] = current_time
                    
                    audit_logger.critical(
                        f"ANOMALY DETECTED: Session {session_id} | Client: {client_name} | Risk Score: {round(risk_score, 4)}"
                    )
                    
                    send_security_alert(
                        session_id=session_id,
                        client_name=client_name,
                        risk_score=round(risk_score, 4),
                        keystrokes=session["total_keystrokes"]
                    )
                else:
                    security_action = "allow" # suppress MFA during cooldown
                    print(f"      ⏳ Alert suppressed (cooling down). {round(120 - (current_time - last_alert))}s remaining.")
        except Exception as e:
            audit_logger.error(f"AI INFERENCE FAILED: Session {session_id} | Error: {str(e)}")
            print(f"   ⚠️ AI model error: {e}. Defaulting to ALLOW.")

    # --- SAVE TO DATABASE ---
    update_session_profile(
        session_id=session_id,
        is_touch=is_touch,
        keys=session["total_keystrokes"],
        mistakes=session["total_corrections"],
        error_rate=round(running_error_rate, 2),
        mouse_dist=round(session["total_mouse_distance_px"], 2),
        scroll_dist=round(session["total_scroll_distance_px"], 2)
    )

    return {"status": "success", "security_action": security_action}


# ========================================================================
#                     ENTERPRISE WEBHOOK INTEGRATION
# ========================================================================

def send_security_alert(session_id: str, client_name: str, risk_score: float, keystrokes: int):
    """Fires a network request to a SOC team's webhook when the AI detects an anomaly."""
    if not WEBHOOK_URL:
        print("   ⚠️ WEBHOOK_URL not configured. Skipping alert dispatch.")
        return
    
    payload = {
        "text": f"🚨 **CRITICAL SECURITY ALERT** 🚨\n\n"
                f"**Client:** {client_name}\n"
                f"**Session ID:** {session_id}\n"
                f"**Risk Score:** {risk_score}\n"
                f"**Status:** The AI detected highly abnormal biometric behavior after {keystrokes} keystrokes. "
                f"The session has been automatically locked and Step-Up MFA has been deployed."
    }
    
    try:
        requests.post(WEBHOOK_URL, json=payload, timeout=2)
        print("   📢 SOC Webhook Alert Dispatched Successfully!")
    except requests.exceptions.RequestException as e:
        print(f"   ⚠️ Failed to dispatch SOC webhook: {e}")


# ========================================================================
#                     CALIBRATION ENDPOINT
# ========================================================================

@app.post("/api/v1/calibrate/complete", tags=["Calibration"])
async def complete_calibration(payload: CalibrationComplete, client_name: str = Depends(verify_api_key)):
    """Triggers personal AI baseline generation after calibration data collection."""
    success = train_user_baseline(payload.session_id)
    if success:
        return {"status": "success", "message": "Baseline AI generated."}
    
    raise HTTPException(status_code=400, detail="Failed to generate baseline. Insufficient calibration data.")


# ========================================================================
#                     ADMIN DASHBOARD (JWT PROTECTED)
# ========================================================================

@app.get("/api/v1/admin/sessions", tags=["Admin"])
async def get_active_sessions(current_user: str = Depends(get_current_user)):
    """Returns the live state of all currently tracked user sessions. Requires JWT authentication."""
    return {"status": "success", "active_sessions": active_sessions}


# ========================================================================
#                     HEALTH CHECK
# ========================================================================

@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint for load balancers and container orchestration."""
    db_healthy = True
    try:
        from database import get_db_connection
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
    except Exception:
        db_healthy = False
    
    models_loaded = (
        ai_models["desktop"]["model"] is not None or
        ai_models["mobile"]["model"] is not None
    )
    
    status_code = 200 if db_healthy else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "healthy" if db_healthy else "degraded",
            "database": "connected" if db_healthy else "disconnected",
            "ai_models": {
                "desktop": "loaded" if ai_models["desktop"]["model"] else "not loaded",
                "mobile": "loaded" if ai_models["mobile"]["model"] else "not loaded"
            },
            "active_sessions": len(active_sessions)
        }
    )


# --- STATIC WEB SERVER MOUNT (must be last) ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIENT_SDK_DIR = os.path.join(BASE_DIR, "client-sdk")
app.mount("/", StaticFiles(directory=CLIENT_SDK_DIR, html=True), name="frontend")