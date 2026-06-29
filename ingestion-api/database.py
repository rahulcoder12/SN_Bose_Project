import sqlite3

DB_FILE = "biometrics.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS session_profiles (
            session_id TEXT PRIMARY KEY,
            is_touch_device INTEGER,  -- NEW: 1 for Mobile/Tablet, 0 for Desktop
            total_keystrokes INTEGER,
            total_corrections INTEGER,
            running_error_rate REAL,
            total_mouse_distance_px REAL,
            total_scroll_distance_px REAL,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def update_session_profile(session_id: str, is_touch: bool, keys: int, mistakes: int, error_rate: float, mouse_dist: float, scroll_dist: float):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Convert boolean to integer for SQLite
    touch_int = 1 if is_touch else 0
    
    cursor.execute('''
        INSERT INTO session_profiles (
            session_id, is_touch_device, total_keystrokes, total_corrections, 
            running_error_rate, total_mouse_distance_px, total_scroll_distance_px
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(session_id) DO UPDATE SET
            total_keystrokes = excluded.total_keystrokes,
            total_corrections = excluded.total_corrections,
            running_error_rate = excluded.running_error_rate,
            total_mouse_distance_px = excluded.total_mouse_distance_px,
            total_scroll_distance_px = excluded.total_scroll_distance_px,
            last_updated = CURRENT_TIMESTAMP
    ''', (session_id, touch_int, keys, mistakes, error_rate, mouse_dist, scroll_dist))
    
    conn.commit()
    conn.close()

def delete_expired_sessions(hours_to_keep=24):
    """
    GDPR/SOC2 Compliance: Deletes biometric session data older than the specified timeframe.
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # SQLite uses the datetime() function to calculate time offsets
    cursor.execute(f'''
        DELETE FROM session_profiles 
        WHERE last_updated <= datetime('now', '-{hours_to_keep} hours')
    ''')
    
    deleted_count = cursor.rowcount
    conn.commit()
    conn.close()
    
    return deleted_count