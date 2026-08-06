"""Unit tests for the biometric feature extraction algorithms."""
from biometrics import extract_keystroke_features, extract_mouse_features, extract_scroll_features


class TestKeystrokeFeatures:
    def test_basic_dwell_time(self):
        """Test that dwell time is calculated correctly from keydown→keyup."""
        events = [
            {"key_code": "KeyA", "event": "down", "t": 100},
            {"key_code": "KeyA", "event": "up", "t": 200},
        ]
        result = extract_keystroke_features(events)
        assert result["avg_dwell_time_ms"] == 100.0
        assert result["total_keystrokes"] == 1

    def test_flight_time_calculation(self):
        """Test that flight time is calculated as the gap between keyup→keydown."""
        events = [
            {"key_code": "KeyA", "event": "down", "t": 100},
            {"key_code": "KeyA", "event": "up", "t": 200},
            {"key_code": "KeyB", "event": "down", "t": 350},
            {"key_code": "KeyB", "event": "up", "t": 450},
        ]
        result = extract_keystroke_features(events)
        assert result["avg_flight_time_ms"] == 150.0  # 350 - 200

    def test_correction_counting(self):
        """Test that Backspace and Delete are counted as corrections."""
        events = [
            {"key_code": "KeyA", "event": "down", "t": 100},
            {"key_code": "KeyA", "event": "up", "t": 200},
            {"key_code": "Backspace", "event": "down", "t": 300},
            {"key_code": "Backspace", "event": "up", "t": 400},
            {"key_code": "Delete", "event": "down", "t": 500},
            {"key_code": "Delete", "event": "up", "t": 600},
        ]
        result = extract_keystroke_features(events)
        assert result["total_corrections"] == 2

    def test_stylometry_word_count(self):
        """Test that space key triggers word count increment."""
        events = [
            {"key_code": "KeyH", "event": "down", "t": 100},
            {"key_code": "KeyH", "event": "up", "t": 150},
            {"key_code": "KeyI", "event": "down", "t": 200},
            {"key_code": "KeyI", "event": "up", "t": 250},
            {"key_code": "Space", "event": "down", "t": 300},
            {"key_code": "Space", "event": "up", "t": 350},
            {"key_code": "KeyY", "event": "down", "t": 400},
            {"key_code": "KeyY", "event": "up", "t": 450},
            {"key_code": "KeyO", "event": "down", "t": 500},
            {"key_code": "KeyO", "event": "up", "t": 550},
        ]
        result = extract_keystroke_features(events)
        # 1 space = 2 words (word before space + word after)
        assert result["stylometry"]["estimated_words"] == 2

    def test_empty_input(self):
        """Test that empty keystroke list doesn't crash."""
        result = extract_keystroke_features([])
        assert result["total_keystrokes"] == 0
        assert result["avg_dwell_time_ms"] == 0
        assert result["avg_flight_time_ms"] == 0
        assert result["total_corrections"] == 0

    def test_error_rate_calculation(self):
        """Test that error rate percentage is correct."""
        events = [
            {"key_code": "KeyA", "event": "down", "t": 100},
            {"key_code": "KeyA", "event": "up", "t": 200},
            {"key_code": "Backspace", "event": "down", "t": 300},
            {"key_code": "Backspace", "event": "up", "t": 400},
        ]
        result = extract_keystroke_features(events)
        # 1 correction out of 2 keystrokes = 50%
        assert result["error_rate_percent"] == 50.0


class TestMouseFeatures:
    def test_basic_distance(self):
        """Test Euclidean distance with a known 3-4-5 triangle."""
        movements = [
            {"x": 0, "y": 0, "t": 100},
            {"x": 3, "y": 4, "t": 200},
        ]
        result = extract_mouse_features(movements)
        assert result["total_distance_px"] == 5.0

    def test_multi_segment_distance(self):
        """Test that distances accumulate across multiple segments."""
        movements = [
            {"x": 0, "y": 0, "t": 100},
            {"x": 3, "y": 4, "t": 200},
            {"x": 6, "y": 8, "t": 300},
        ]
        result = extract_mouse_features(movements)
        assert result["total_distance_px"] == 10.0  # Two 3-4-5 triangles

    def test_single_point_returns_empty(self):
        """Test that < 2 points returns empty dict (can't compute distance)."""
        result = extract_mouse_features([{"x": 0, "y": 0, "t": 100}])
        assert result == {}

    def test_zero_time_delta_handled(self):
        """Test that simultaneous events don't cause division by zero."""
        movements = [
            {"x": 0, "y": 0, "t": 100},
            {"x": 10, "y": 10, "t": 100},  # Same timestamp
        ]
        result = extract_mouse_features(movements)
        # Should not crash — the zero-dt event is skipped

    def test_velocity_calculation(self):
        """Test that velocity is distance/time in px/ms."""
        movements = [
            {"x": 0, "y": 0, "t": 0},
            {"x": 100, "y": 0, "t": 1000},  # 100px in 1000ms
        ]
        result = extract_mouse_features(movements)
        assert result["avg_velocity_px_ms"] == 0.1  # 100/1000

    def test_empty_input_returns_empty(self):
        """Test that empty list returns empty dict."""
        result = extract_mouse_features([])
        assert result == {}


class TestScrollFeatures:
    def test_basic_scroll_distance(self):
        """Test total scroll distance calculation."""
        scrolls = [
            {"y": 0, "t": 100},
            {"y": 500, "t": 200},
        ]
        result = extract_scroll_features(scrolls)
        assert result["total_scroll_distance_px"] == 500
        assert result["max_scroll_depth_px"] == 500

    def test_bidirectional_scroll(self):
        """Test that scrolling up and down accumulates total distance."""
        scrolls = [
            {"y": 0, "t": 100},
            {"y": 500, "t": 200},
            {"y": 200, "t": 300},  # Scrolled back up 300px
        ]
        result = extract_scroll_features(scrolls)
        assert result["total_scroll_distance_px"] == 800  # 500 + 300
        assert result["max_scroll_depth_px"] == 200  # Final position

    def test_single_point_returns_empty(self):
        """Test that < 2 scroll events returns empty dict."""
        result = extract_scroll_features([{"y": 0, "t": 100}])
        assert result == {}

    def test_no_movement(self):
        """Test that staying at same position reports zero distance."""
        scrolls = [
            {"y": 100, "t": 100},
            {"y": 100, "t": 200},
        ]
        result = extract_scroll_features(scrolls)
        assert result["total_scroll_distance_px"] == 0
