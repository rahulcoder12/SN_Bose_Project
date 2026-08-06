"""
JWT Authentication utilities for the Zero Trust Auth API.
Handles token creation, verification, and FastAPI dependency injection.
"""
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Header, status
from jose import JWTError, jwt
from dotenv import load_dotenv

load_dotenv()

# --- CONFIGURATION ---
SECRET_KEY = os.getenv("SECRET_KEY", "CHANGE-ME-IN-PRODUCTION-minimum-32-chars")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

# --- MULTI-TENANT API KEYS (loaded from env) ---
VALID_API_KEYS = {}

_key1 = os.getenv("API_KEY_1")
_key2 = os.getenv("API_KEY_2")
if _key1:
    VALID_API_KEYS[_key1] = "Acme Bank Corp"
if _key2:
    VALID_API_KEYS[_key2] = "Global E-Commerce Store"


# --- TOKEN CREATION ---
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Creates a signed JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict) -> str:
    """Creates a long-lived refresh token for session renewal."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


# --- TOKEN VERIFICATION ---
def verify_token(token: str, expected_type: str = "access") -> dict:
    """Decodes and validates a JWT token. Raises HTTPException if invalid."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != expected_type:
            raise HTTPException(status_code=401, detail="Invalid token type")
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


# --- FASTAPI DEPENDENCIES ---
async def get_current_user(authorization: str = Header(None)) -> str:
    """
    FastAPI dependency that extracts and validates the JWT from the Authorization header.
    
    Usage in endpoints:
        @app.get("/protected")
        async def my_endpoint(current_user: str = Depends(get_current_user)):
            ...
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header. Use: Bearer <token>"
        )
    
    token = authorization.split(" ")[1]
    payload = verify_token(token)
    username = payload.get("sub")
    
    if not username:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    
    return username


async def verify_api_key(x_api_key: str = Header(None, description="Your Enterprise API Key")) -> str:
    """
    FastAPI dependency that validates the enterprise API key.
    Returns the client name associated with the key.
    
    Usage in endpoints:
        @app.post("/api-key-protected")
        async def my_endpoint(client_name: str = Depends(verify_api_key)):
            ...
    """
    if not x_api_key or x_api_key not in VALID_API_KEYS:
        raise HTTPException(status_code=401, detail="Invalid or missing API Key")
    
    return VALID_API_KEYS[x_api_key]
