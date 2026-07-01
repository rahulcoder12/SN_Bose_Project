import os
import psycopg2
from dotenv import load_dotenv

# Load the secret connection string from the .env file
load_dotenv()
DB_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    """Establishes a secure connection to the cloud PostgreSQL database."""
    return psycopg2.connect(DB_URL)

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    # PostgreSQL uses different syntax for tables and booleans
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

    conn.commit()
    conn.close()

def is_username_taken(username):
    """Queries the database to see if the username already exists."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM users WHERE username = %s", (username,))
    user = cursor.fetchone()
    conn.close()
    return user is not None # Returns True if taken, False if available

def register_new_user(username, password):
    """Saves the new user to PostgreSQL."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO users (username, password_hash) VALUES (%s, %s)", (username, password))
    conn.commit()
    conn.close()

def update_session_profile(session_id, is_touch, keys, mistakes, error_rate, mouse_dist, scroll_dist):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # PostgreSQL uses %s for safe variable injection and ON CONFLICT for upserts
    cursor.execute('''
        INSERT INTO session_profiles 
        (session_id, is_touch_device, keys_pressed, mistakes_made, error_rate, mouse_distance_px, scroll_distance_px, last_updated)
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
    
    conn.commit()
    conn.close()

def delete_expired_sessions(hours_to_keep=24):
    conn = get_db_connection()
    cursor = conn.cursor()
    # PostgreSQL uses native INTERVAL syntax for time math
    cursor.execute(f'''
        DELETE FROM session_profiles 
        WHERE last_updated <= NOW() - INTERVAL '{hours_to_keep} hours'
    ''')
    
    deleted_count = cursor.rowcount
    conn.commit()
    conn.close()
    
    return deleted_count

def verify_login(username, password):
    """Checks if the username and password match the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT password_hash FROM users WHERE username = %s", (username,))
    user = cursor.fetchone()
    conn.close()
    
    if user and user[0] == password:
        return True
    return False

def get_password_age(username):
    """Calculates how many days are left until the 90-day expiration."""
    conn = get_db_connection()
    cursor = conn.cursor()
    # PostgreSQL math to get the difference in days
    cursor.execute("SELECT EXTRACT(DAY FROM CURRENT_TIMESTAMP - created_at) FROM users WHERE username = %s", (username,))
    age = cursor.fetchone()
    conn.close()
    
    if age:
        days_active = int(age[0])
        return max(0, 90 - days_active)
    return 0

def update_password(username, new_password):
    """Regenerates the password and resets the 90-day timer."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE users 
        SET password_hash = %s, created_at = CURRENT_TIMESTAMP 
        WHERE username = %s
    ''', (new_password, username))
    conn.commit()
    conn.close()