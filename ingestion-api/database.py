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