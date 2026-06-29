import math
from typing import List, Dict

def extract_keystroke_features(keystrokes: List[Dict]) -> Dict:
    dwell_times = []
    flight_times = []
    active_keys = {}
    last_keyup_time = None
    
    # Core biometrics counters
    correction_count = 0
    
    # Stylometry counters
    word_count = 0
    sentence_count = 0
    total_character_keys = 0

    for event in keystrokes:
        key = event["key_code"]
        action = event["event"]
        t = event["t"]

        if action == "down":
            # 1. Track Errors
            if key in ["Backspace", "Delete"]:
                correction_count += 1
                
            # 2. Track Stylometry (Structure)
            elif key == "Space":
                word_count += 1
            elif key in ["Period", "Enter"]:
                sentence_count += 1
            # Assuming standard letters/numbers start with 'Key' or 'Digit'
            elif key.startswith("Key") or key.startswith("Digit"):
                total_character_keys += 1

            # 3. Calculate Flight Time
            if last_keyup_time is not None:
                flight = t - last_keyup_time
                if flight < 2000: 
                    flight_times.append(flight)
            
            active_keys[key] = t

        elif action == "up":
            # 4. Calculate Dwell Time
            if key in active_keys:
                dwell = t - active_keys[key]
                dwell_times.append(dwell)
                del active_keys[key]
            
            last_keyup_time = t

    # Averages for Dynamics
    avg_dwell = sum(dwell_times) / len(dwell_times) if dwell_times else 0
    avg_flight = sum(flight_times) / len(flight_times) if flight_times else 0
    total_keys_pressed = len(dwell_times)
    error_rate = (correction_count / total_keys_pressed * 100) if total_keys_pressed > 0 else 0

    # Averages for Stylometry
    # +1 to word_count to account for the last word typed before a pause
    adjusted_words = word_count + 1 if total_character_keys > 0 else 0
    avg_word_length = total_character_keys / adjusted_words if adjusted_words > 0 else 0

    return {
        "total_keystrokes": total_keys_pressed,
        "avg_dwell_time_ms": round(avg_dwell, 2),
        "avg_flight_time_ms": round(avg_flight, 2),
        "total_corrections": correction_count,
        "error_rate_percent": round(error_rate, 2),
        "stylometry": {
            "estimated_words": adjusted_words,
            "estimated_sentences": sentence_count,
            "avg_word_length": round(avg_word_length, 1)
        }
    }

def extract_mouse_features(mouse_movements: List[Dict]) -> Dict:
    """
    Calculates distance and velocity from raw mouse coordinates.
    """
    if len(mouse_movements) < 2:
        return {}

    velocities = []
    distances = []

    for i in range(1, len(mouse_movements)):
        p1 = mouse_movements[i-1]
        p2 = mouse_movements[i]

        # Calculate difference in coordinates and time
        dx = p2["x"] - p1["x"]
        dy = p2["y"] - p1["y"]
        dt = p2["t"] - p1["t"]

        # Prevent division by zero if two events fire at the exact same millisecond
        if dt == 0:
            continue

        # Euclidean Distance: d = √((x2 - x1)² + (y2 - y1)²)
        distance = math.sqrt(dx**2 + dy**2)
        
        # Velocity = Distance / Time (pixels per millisecond)
        velocity = distance / dt  

        distances.append(distance)
        velocities.append(velocity)

    avg_velocity = sum(velocities) / len(velocities) if velocities else 0
    total_distance = sum(distances)

    return {
        "total_movements": len(mouse_movements),
        "total_distance_px": round(total_distance, 2),
        "avg_velocity_px_ms": round(avg_velocity, 4)
    }

def extract_scroll_features(scrolls: List[Dict]) -> Dict:
    """
    Calculates scroll depth, distance, and reading cadence.
    """
    if len(scrolls) < 2:
        return {}

    total_distance = 0
    
    for i in range(1, len(scrolls)):
        # Calculate the absolute distance moved between the 100ms captures
        dy = abs(scrolls[i]["y"] - scrolls[i-1]["y"])
        total_distance += dy

    return {
        "total_scroll_events": len(scrolls),
        "total_scroll_distance_px": total_distance,
        "max_scroll_depth_px": scrolls[-1]["y"] # How far down they ended up
    }