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
    
    // Check if we already injected it
    if (document.getElementById("zt-mfa-overlay")) return;

    // Create a full-screen overlay
    const overlay = document.createElement("div");
    overlay.id = "zt-mfa-overlay";
    overlay.style.position = "fixed";
    overlay.style.top = "0";
    overlay.style.left = "0";
    overlay.style.width = "100vw";
    overlay.style.height = "100vh";
    overlay.style.backgroundColor = "rgba(15, 23, 42, 0.95)";
    overlay.style.backdropFilter = "blur(10px)";
    overlay.style.zIndex = "2147483647"; // Max z-index
    overlay.style.display = "flex";
    overlay.style.flexDirection = "column";
    overlay.style.justifyContent = "center";
    overlay.style.alignItems = "center";
    overlay.style.color = "white";
    overlay.style.fontFamily = "sans-serif";

    overlay.innerHTML = `
      <div style="background: #1e293b; padding: 40px; border-radius: 12px; text-align: center; max-width: 400px; box-shadow: 0 10px 25px rgba(0,0,0,0.5);">
        <h2 style="color: #ef4444; margin-top: 0;">🚨 Security Lockdown</h2>
        <p style="color: #94a3b8; margin-bottom: 20px;">Abnormal behavior detected. Please verify your identity to continue your session.</p>
        <input type="password" id="zt-mfa-password" placeholder="Enter your password" style="width: 100%; padding: 12px; margin-bottom: 15px; border-radius: 6px; border: 1px solid #334155; background: #0f172a; color: white; box-sizing: border-box;">
        <button id="zt-mfa-submit" style="width: 100%; padding: 12px; border-radius: 6px; border: none; background: #38bdf8; color: #0f172a; font-weight: bold; cursor: pointer;">Verify Identity</button>
        <p id="zt-mfa-error" style="color: #ef4444; font-size: 14px; margin-top: 15px; display: none;">⚠️ Incorrect password.</p>
      </div>
    `;

    document.body.appendChild(overlay);

    const input = document.getElementById("zt-mfa-password");
    input.focus();

    // Prevent scrolling behind the overlay
    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const submitBtn = document.getElementById("zt-mfa-submit");
    const errorMsg = document.getElementById("zt-mfa-error");

    const verifyPassword = () => {
        chrome.storage.local.get(['recoveryPassword'], (result) => {
            if (input.value === result.recoveryPassword) {
                // Unlock
                document.body.removeChild(overlay);
                document.body.style.overflow = originalOverflow;
                
                // Clear old anomalous events and resume tracking
                this.resetBuffer(); 
                this.flushInterval = setInterval(() => { this.flush(); }, 5000); 
            } else {
                errorMsg.style.display = "block";
                input.value = "";
                input.focus();
            }
        });
    };

    submitBtn.addEventListener("click", verifyPassword);
    input.addEventListener("keypress", (e) => {
        if (e.key === "Enter") verifyPassword();
    });
  }
  async flush() {
    // 1. Check if there is actually any data to send. If the user is idle, do nothing.
    if (this.buffer.keystrokes.length === 0 && this.buffer.mouse_movements.length === 0 && this.buffer.clicks.length === 0) {
      return;
    }

    // 2. Package the payload according to our Day 1 Schema
    const payload = {
      session_id: this.sessionId,
      timestamp_start: Date.now() - 5000,
      timestamp_end: Date.now(),
      is_calibration: this.isCalibrationMode || false,
      device_context: {
        user_agent: navigator.userAgent,
        screen_resolution: `${window.screen.width}x${window.screen.height}`,
        platform: navigator.platform,
        is_touch_device: ('ontouchstart' in window) || (navigator.maxTouchPoints > 0)
      },
      events: this.buffer
    };

    // 3. Clear the main buffer immediately so we don't miss new events while sending
    this.resetBuffer();

    // 4. Send the data to the backend API
    // 4. Send the data to the Background Service Worker (Bypasses CORS)
    try {
      chrome.runtime.sendMessage({
          action: "FLUSH_TELEMETRY",
          payload: payload,
          apiKey: this.apiKey
      }, (response) => {
          if (response && response.status === "success") {
              console.log("Telemetry flushed via Service Worker. Verdict:", response.data);
              
              // --- THE ACTION GATEWAY ---
              if (response.data.security_action === "require_mfa") {
                  this.triggerLockdown();
              }
          } else {
              console.error("Service worker failed to deliver payload:", response);
          }
      });
    } catch (error) {
      console.error("Failed to communicate with Background Worker:", error);
    }
  }
}

// --- THE GATEKEEPER ---
// Only start tracking if the user has passed the initial calibration
chrome.storage.local.get(['isCalibrated'], function(result) {
    if (result.isCalibrated) {
        console.log("🛡️ Zero Trust Enterprise Shield: Calibrated and Active.");
        const tracker = new BehaviorTracker("sk_live_51Mabcde12345");
    } else {
        console.log("⚠️ Zero Trust: Calibration pending. Tracker paused.");
    }
});