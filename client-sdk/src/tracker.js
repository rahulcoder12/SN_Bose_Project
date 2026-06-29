class BehaviorTracker {
  constructor(apiKey) {
    if (!apiKey) {
      console.error("Zero Trust SDK Error: Missing API Key.");
      return;
    }
    this.apiKey = apiKey; // Store the key

    this.sessionId = this.initSession();
    this.resetBuffer(); 
    
    this.lastMouseTime = 0;
    this.mouseThrottleMs = 50; 
    
    this.lastScrollTime = 0;
    this.scrollThrottleMs = 100;

    this.initListeners();

    this.flushInterval = setInterval(() => {
      this.flush();
    }, 5000);
  }

  initSession() {
    // Check if a session ID already exists for this tab
    let sid = sessionStorage.getItem('zta_session_id');
    if (!sid) {
      // Generate a secure UUID (or fallback for older browsers)
      if (window.crypto && crypto.randomUUID) {
        sid = crypto.randomUUID();
      } else {
        sid = 'sess_' + Math.random().toString(36).substring(2, 15);
      }
      sessionStorage.setItem('zta_session_id', sid);
    }
    return sid;
  }

  initListeners() {
    // Keyboard Listeners
    window.addEventListener('keydown', (e) => this.trackKey(e, 'down'));
    window.addEventListener('keyup', (e) => this.trackKey(e, 'up'));

    // Mouse Listeners
    window.addEventListener('mousemove', (e) => this.trackMouseMove(e));
    window.addEventListener('mousedown', (e) => this.trackClick(e));

    // NEW: Scroll Listener
    window.addEventListener('scroll', () => this.trackScroll());
  }

  trackMouseMove(e) {
    const now = performance.now();
    
    // Only record if 50ms have passed since the last capture
    if (now - this.lastMouseTime > this.mouseThrottleMs) {
      this.buffer.mouse_movements.push({
        x: e.clientX,
        y: e.clientY,
        t: Math.round(now)
      });
      this.lastMouseTime = now;
    }
  }

  trackClick(e) {
    // Identify which button was clicked
    let btn = 'unknown';
    if (e.button === 0) btn = 'left';
    if (e.button === 1) btn = 'middle';
    if (e.button === 2) btn = 'right';

    this.buffer.clicks.push({
      x: e.clientX,
      y: e.clientY,
      button: btn,
      t: Math.round(performance.now())
    });
  }

  trackKey(e, type) {
    // Ignore repeating keys if the user holds a key down long enough to trigger auto-repeat
    if (type === 'down' && e.repeat) return;

    this.buffer.keystrokes.push({
      key_code: e.code,
      event: type,
      t: Math.round(performance.now())
    });
  }

  trackScroll() {
    const now = performance.now();
    if (now - this.lastScrollTime > this.scrollThrottleMs) {
      this.buffer.scrolls.push({
        y: Math.round(window.scrollY), // How far down the page they are
        t: Math.round(now)
      });
      this.lastScrollTime = now;
    }
  }

  resetBuffer() {
    this.buffer = {
      keystrokes: [],
      mouse_movements: [],
      clicks: [],
      scrolls: []
    };
    this.sessionStartTime = Math.round(performance.now());
  }
  
  triggerLockdown() {
    console.warn("🚨 ANOMALY DETECTED: Triggering Session Lockdown!");
    
    // Stop flushing data to the server
    clearInterval(this.flushInterval);
    
    // Look for an MFA overlay in the HTML and display it
    const overlay = document.getElementById("mfa-overlay");
    if (overlay) {
      overlay.style.display = "flex";
    } else {
      // Fallback if the HTML hasn't been updated yet
      alert("SECURITY ALERT: Abnormal behavior detected. Please verify your identity.");
    }
  }
  async flush() {
    // 1. Check if there is actually any data to send. If the user is idle, do nothing.
    if (this.buffer.keystrokes.length === 0 && this.buffer.mouse_movements.length === 0 && this.buffer.clicks.length === 0) {
      return;
    }

    // 2. Package the payload according to our Day 1 Schema
    const payload = {
      session_id: this.sessionId,
      timestamp_start: Math.min(...this.buffer.keystrokes.map(k => k.t), ...this.buffer.mouse_movements.map(m => m.t), Date.now()),
      timestamp_end: Date.now(),
      is_calibration: this.isCalibrationMode || false, // NEW: Tell the backend if we are establishing a baseline
      device_context: {
        user_agent: navigator.userAgent,
        screen_resolution: `${window.screen.width}x${window.screen.height}`,
        platform: navigator.platform,
        is_touch_device: ('ontouchstart' in window) || (navigator.maxTouchPoints > 0)
      },
      events: this.buffer
    };
      events: {
        keystrokes: [...this.buffer.keystrokes],
        mouse_movements: [...this.buffer.mouse_movements],
        clicks: [...this.buffer.clicks],
        scrolls: [...this.buffer.scrolls]
      }
    };

    // 3. Clear the main buffer immediately so we don't miss new events while sending
    this.resetBuffer();

    // 4. Send the data to the backend API
    try {
      const response = await fetch('http://localhost:8000/api/v1/ingest', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'x-api-key': this.apiKey  // NEW: Authenticate the client
        },
        body: JSON.stringify(payload),
        keepalive: true 
      });

      if (response.ok) {
        const result = await response.json();
        console.log("Telemetry flushed. Server response:", result);

        // --- THE ACTION GATEWAY ---
        if (result.security_action === "require_mfa") {
          this.triggerLockdown();
        }
      } else {
        console.error("Failed to send telemetry payload", response.status);
      }
    } catch (error) {
      console.error("Network error during telemetry flush:", error);
    }
  }
}
