import os
import bcrypt
import psycopg2
from psycopg2 import pool
from dotenv import load_dotenv
from contextlib import contextmanager

# Load the secret connection string from the .env file
load_dotenv()
DB_URL = os.getenv("DATABASE_URL")

# --- CONNECTION POOL ---
# Reuse connections instead of opening/closing TCP sockets per query
connection_pool = None

def init_pool():
    """Initialize the database connection pool (min 2, max 10 connections)."""
    global connection_pool
    connection_pool = psycopg2.pool.ThreadedConnectionPool(
        minconn=2,
        maxconn=10,
        dsn=DB_URL
    )
    print("   ✅ Database connection pool initialized (2-10 connections).")

@contextmanager
def get_db_connection():
    """
    Context manager that borrows a connection from the pool
    and safely returns it when done. Auto-commits on success, rolls back on error.
    """
    conn = connection_pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        connection_pool.putconn(conn)


# --- TABLE INITIALIZATION ---
def init_db():
    """Creates the required tables and indexes if they don't already exist."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS session_profiles (
                session_id TEXT PRIMARY KEY,
                is_touch_device BOOLEAN,
                keys_pressed INTEGER,
                mistakes_made INTEGER,
                error_rate REAL,
                mouse_distance_px REAL,
                scroll_distance_px REAL,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password_hash TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Performance index for GDPR time-range deletion queries
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_session_last_updated 
            ON session_profiles (last_updated)
        ''')


# --- USER MANAGEMENT ---
def is_username_taken(username):
    """Queries the database to see if the username already exists."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT username FROM users WHERE username = %s", (username,))
        return cursor.fetchone() is not None


def register_new_user(username, password):
    """Hashes the password with bcrypt and saves the new user to PostgreSQL."""
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password_bytes, salt)
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (username, password_hash) VALUES (%s, %s)",
            (username, hashed.decode('utf-8'))
        )


def verify_login(username, password):
    """Checks if the password matches the bcrypt hash stored in the database."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT password_hash FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
    
    if user:
        stored_hash = user[0].encode('utf-8')
        return bcrypt.checkpw(password.encode('utf-8'), stored_hash)
    return False


def get_password_age(username):
    """Calculates how many days are left until the 90-day expiration."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT EXTRACT(DAY FROM CURRENT_TIMESTAMP - created_at) FROM users WHERE username = %s",
            (username,)
        )
        age = cursor.fetchone()
    
    if age:
        days_active = int(age[0])
        return max(0, 90 - days_active)
    return 0


def update_password(username, new_password):
    """Hashes the new password with bcrypt, saves it, and resets the 90-day timer."""
    hashed = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt(rounds=12))
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE users 
            SET password_hash = %s, created_at = CURRENT_TIMESTAMP 
            WHERE username = %s
        ''', (hashed.decode('utf-8'), username))


# --- SESSION PROFILE MANAGEMENT ---
def update_session_profile(session_id, is_touch, keys, mistakes, error_rate, mouse_dist, scroll_dist):
    """Upserts a session's biometric profile into PostgreSQL."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO session_profiles 
            (session_id, is_touch_device, keys_pressed, mistakes_made, error_rate, 
             mouse_distance_px, scroll_distance_px, last_updated)
            VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (session_id) 
            DO UPDATE SET 
                is_touch_device = EXCLUDED.is_touch_device,
                keys_pressed = EXCLUDED.keys_pressed,
                mistakes_made = EXCLUDED.mistakes_made,
                error_rate = EXCLUDED.error_rate,
                mouse_distance_px = EXCLUDED.mouse_distance_px,
                scroll_distance_px = EXCLUDED.scroll_distance_px,
                last_updated = CURRENT_TIMESTAMP
        ''', (session_id, is_touch, keys, mistakes, error_rate, mouse_dist, scroll_dist))


def delete_expired_sessions(hours_to_keep=24):
    """GDPR-compliant: permanently deletes session data older than the specified hours."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM session_profiles WHERE last_updated <= NOW() - INTERVAL '%s hours'",
            (hours_to_keep,)
        )
        return cursor.rowcount