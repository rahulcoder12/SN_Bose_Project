/**
 * Zero Trust Enterprise Shield — content.js
 * Continuous behavioral biometric authentication + content pattern analysis.
 * Runs on every page (excluding localhost) after calibration is complete.
 */
class BehaviorTracker {
  constructor(apiKey) {
    if (!apiKey) { console.error("[ZeroTrust] Missing API Key."); return; }
    this.apiKey = apiKey;

    this.sessionId   = this.initSession();
    this.resetBuffer();

    this.lastMouseTime    = 0;
    this.mouseThrottleMs  = 50;
    this.lastScrollTime   = 0;
    this.scrollThrottleMs = 100;

    // ── Content Analysis ──────────────────────────────────────
    this.currentWordBuffer = '';
    this.typedWords        = [];   // Rolling last-200 typed words

    // ── Anomaly Strike Tracking ───────────────────────────────
    this.anomalyStrikes = 0;
    this.isLockedDown   = false;

    // ── Calibration Reference (links monitoring to trained model) ──
    this.calibrationSessionId = null;

    // Load persistent state from chrome.storage
    chrome.storage.local.get(['anomalyStrikes', 'calibrationSessionId'], (result) => {
      this.anomalyStrikes       = result.anomalyStrikes       || 0;
      this.calibrationSessionId = result.calibrationSessionId || null;
    });

    this.initListeners();
    // Flush telemetry every 5 seconds
    this.flushInterval = setInterval(() => this.flush(), 5000);
  }

  // ── SESSION ────────────────────────────────────────────────
  initSession() {
    // If running inside an iframe, try to reuse the top frame's session ID
    // so all keystrokes from the page (including iframe editors) appear in one session.
    try {
      if (window !== window.top && window.top.sessionStorage.getItem('zta_session_id')) {
        return window.top.sessionStorage.getItem('zta_session_id');
      }
    } catch (_) { /* cross-origin top frame — use own session */ }

    let sid = sessionStorage.getItem('zta_session_id');
    if (!sid) {
      sid = (window.crypto && crypto.randomUUID)
        ? crypto.randomUUID()
        : 'sess_' + Math.random().toString(36).substring(2, 15);
      sessionStorage.setItem('zta_session_id', sid);
    }
    return sid;
  }

  // ── EVENT LISTENERS ────────────────────────────────────────
  initListeners() {
    // Use capture:true so events are caught before any editor can stop propagation
    window.addEventListener('keydown',   (e) => this.trackKey(e, 'down'), true);
    window.addEventListener('keyup',     (e) => this.trackKey(e, 'up'),   true);
    window.addEventListener('mousemove', (e) => this.trackMouseMove(e));
    window.addEventListener('mousedown', (e) => this.trackMouseAction(e, 'down'));
    window.addEventListener('mouseup',   (e) => this.trackMouseAction(e, 'up'));
    window.addEventListener('scroll',    ()  => this.trackScroll());
    // Also listen on document for editors that attach to document instead of window
    document.addEventListener('keydown', (e) => this.trackKey(e, 'down'), true);
    document.addEventListener('keyup',   (e) => this.trackKey(e, 'up'),   true);
  }

  trackMouseMove(e) {
    const now = performance.now();
    if (now - this.lastMouseTime > this.mouseThrottleMs) {
      this.buffer.mouse_movements.push({ x: e.clientX, y: e.clientY, t: Math.round(now) });
      this.lastMouseTime = now;
    }
  }

  trackMouseAction(e, type) {
    const btnMap = { 0: 'left', 1: 'middle', 2: 'right' };
    this.buffer.clicks.push({
      x: e.clientX, y: e.clientY,
      button: btnMap[e.button] || 'unknown',
      event: type,
      t: Math.round(performance.now())
    });
  }

  trackKey(e, type) {
    if (type === 'down' && e.repeat) return;
    // Deduplicate: document and window both fire — skip if same event was already recorded
    const now = Math.round(performance.now());
    if (this._lastKeyTs === now && this._lastKeyCode === (e.code || e.key)) return;
    this._lastKeyTs   = now;
    this._lastKeyCode = e.code || e.key;

    this.buffer.keystrokes.push({
      key_code: e.code || e.key || 'Key',
      event:    type,
      t:        Math.round(performance.now())
    });

    // ── Content Analysis: extract words from keystrokes ──────
    if (type === 'down') {
      const sep = ['Space','Enter','Tab'].includes(e.code) ||
                  [' ',',','.',';','!','?'].includes(e.key);
      if (sep) {
        if (this.currentWordBuffer.length > 0) {
          this.typedWords.push(this.currentWordBuffer);
          if (this.typedWords.length > 200) this.typedWords.shift();
          this.currentWordBuffer = '';
        }
      } else if (e.code === 'Backspace') {
        this.currentWordBuffer = this.currentWordBuffer.slice(0, -1);
      } else if (e.key && e.key.length === 1) {
        this.currentWordBuffer += e.key;
      }
    }

    // Instant flush on burst of 6+ keystrokes
    if (this.buffer.keystrokes.length >= 6) this.flush();
  }

  trackScroll() {
    const now = performance.now();
    if (now - this.lastScrollTime > this.scrollThrottleMs) {
      this.buffer.scrolls.push({ y: Math.round(window.scrollY), t: Math.round(now) });
      this.lastScrollTime = now;
    }
  }

  // ── CONTENT ANALYSIS ──────────────────────────────────────
  getContentFeatures() {
    const words = this.typedWords.filter(w => w.length > 0);
    if (words.length < 5) return null;

    // Gibberish: words with no vowels (length > 2) = random keysmash
    const vowelRe       = /[aeiouAEIOU]/;
    const gibberishCount = words.filter(w => !vowelRe.test(w) && w.length > 2).length;
    const gibberishRatio = gibberishCount / words.length;

    const avgWordLength  = words.reduce((s, w) => s + w.length, 0) / words.length;
    const uniqueWords    = new Set(words.map(w => w.toLowerCase()));
    const vocabRichness  = uniqueWords.size / words.length;

    const allChars  = words.join('');
    const capsRatio = (allChars.match(/[A-Z]/g) || []).length / (allChars.length || 1);

    return {
      avg_word_length:     Math.round(avgWordLength  * 100) / 100,
      gibberish_ratio:     Math.round(gibberishRatio * 100) / 100,
      vocabulary_richness: Math.round(vocabRichness  * 100) / 100,
      caps_ratio:          Math.round(capsRatio       * 100) / 100,
      word_count:          words.length
    };
  }

  // ── BUFFER ────────────────────────────────────────────────
  resetBuffer() {
    this.buffer = { keystrokes: [], mouse_movements: [], clicks: [], scrolls: [] };
    this.sessionStartTime = Math.round(performance.now());
  }

  // ── LOCKDOWN & FORCE LOGOUT ───────────────────────────────
  triggerLockdown() {
    if (this.isLockedDown) return;   // Already showing overlay

    this.isLockedDown = true;
    this.anomalyStrikes++;
    chrome.storage.local.set({ anomalyStrikes: this.anomalyStrikes });
    clearInterval(this.flushInterval);
    document.body.style.overflow = 'hidden';

    console.warn(`[ZeroTrust] 🚨 ANOMALY STRIKE ${this.anomalyStrikes}/3`);

    if (this.anomalyStrikes >= 3) {
      this.forceLogout();
      return;
    }

    // Remove any stale overlay first
    const stale = document.getElementById('zt-mfa-overlay');
    if (stale) stale.remove();

    document.body.appendChild(this._buildMFAOverlay());
    const inp = document.getElementById('zt-mfa-password');
    if (inp) inp.focus();
  }

  _buildMFAOverlay() {
    const overlay = document.createElement('div');
    overlay.id    = 'zt-mfa-overlay';
    Object.assign(overlay.style, {
      position:       'fixed',
      top:            '0', left: '0',
      width:          '100vw', height: '100vh',
      background:     'rgba(10,15,30,0.97)',
      backdropFilter: 'blur(14px)',
      zIndex:         '2147483647',
      display:        'flex',
      flexDirection:  'column',
      justifyContent: 'center',
      alignItems:     'center',
      fontFamily:     "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif"
    });

    const remaining = 3 - this.anomalyStrikes;
    overlay.innerHTML = `
      <div style="background:#1e293b;padding:45px 40px;border-radius:16px;
                  text-align:center;max-width:420px;width:90%;
                  border:2px solid #ef4444;box-shadow:0 25px 60px rgba(0,0,0,0.85);">
        <div style="font-size:54px;margin-bottom:12px;">🚨</div>
        <h2 style="color:#ef4444;margin:0 0 8px;font-size:22px;">Security Lockdown</h2>
        <p style="color:#94a3b8;font-size:14px;margin:0 0 6px;">
          Anomalous behavior detected by the AI engine.
        </p>
        <p style="color:#64748b;font-size:12px;margin:0 0 22px;">
          Strike <strong style="color:#f59e0b;font-size:14px;">${this.anomalyStrikes}</strong>
          of 3 &mdash;
          <strong style="color:#ef4444;">${remaining}</strong>
          remaining before forced account logout.
        </p>
        <input type="password" id="zt-mfa-password"
          placeholder="Enter your recovery password"
          style="width:100%;padding:13px;border-radius:8px;
                 border:1px solid #334155;background:#0f172a;
                 color:white;box-sizing:border-box;font-size:15px;
                 margin-bottom:12px;outline:none;">
        <button id="zt-mfa-submit"
          style="width:100%;padding:13px;border-radius:8px;border:none;
                 background:#38bdf8;color:#0f172a;font-weight:700;
                 cursor:pointer;font-size:15px;transition:opacity 0.2s;">
          Verify Identity
        </button>
        <p id="zt-mfa-error"
          style="color:#ef4444;font-size:13px;margin-top:12px;
                 display:none;background:rgba(239,68,68,0.1);
                 padding:8px 12px;border-radius:6px;border:1px solid rgba(239,68,68,0.3);">
          ⚠️ Incorrect password. Please try again.
        </p>
      </div>
    `;

    const verify = () => {
      const input   = document.getElementById('zt-mfa-password');
      const btn     = document.getElementById('zt-mfa-submit');
      const errorEl = document.getElementById('zt-mfa-error');
      if (!input || !btn) return;

      btn.disabled    = true;
      btn.textContent = 'Verifying…';

      chrome.storage.local.get(['recoveryPassword'], (result) => {
        if (input.value === result.recoveryPassword) {
          // ✅ Correct — reset strikes and resume
          this.anomalyStrikes = 0;
          chrome.storage.local.set({ anomalyStrikes: 0 });
          overlay.remove();
          document.body.style.overflow = '';
          this.isLockedDown = false;
          this.resetBuffer();
          this.flushInterval = setInterval(() => this.flush(), 5000);
        } else {
          if (errorEl) errorEl.style.display = 'block';
          input.value      = '';
          btn.disabled     = false;
          btn.textContent  = 'Verify Identity';
          input.focus();
        }
      });
    };

    overlay.addEventListener('DOMNodeInserted', () => {}, { once: true });  // force repaint
    setTimeout(() => {
      const btn   = document.getElementById('zt-mfa-submit');
      const input = document.getElementById('zt-mfa-password');
      if (btn)   btn.addEventListener('click', verify);
      if (input) input.addEventListener('keydown', (e) => { if (e.key === 'Enter') verify(); });
    }, 0);

    return overlay;
  }

  forceLogout() {
    console.error('[ZeroTrust] 🔴 3 STRIKES — Forced logout initiated.');

    // Clear all auth tokens
    try { sessionStorage.clear(); } catch (_) {}
    try {
      ['accessToken','refreshToken','zta_session_id','activeUser'].forEach(k => {
        localStorage.removeItem(k);
        sessionStorage.removeItem(k);
      });
    } catch (_) {}

    // Reset strike counter
    chrome.storage.local.set({ anomalyStrikes: 0 });

    // Remove MFA overlay if present
    const old = document.getElementById('zt-mfa-overlay');
    if (old) old.remove();

    // Build forced-logout overlay
    const overlay = document.createElement('div');
    overlay.id    = 'zt-logout-overlay';
    Object.assign(overlay.style, {
      position:       'fixed',
      top:            '0', left: '0',
      width:          '100vw', height: '100vh',
      background:     'rgba(10,15,30,0.99)',
      backdropFilter: 'blur(20px)',
      zIndex:         '2147483647',
      display:        'flex',
      flexDirection:  'column',
      justifyContent: 'center',
      alignItems:     'center',
      fontFamily:     "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif"
    });

    overlay.innerHTML = `
      <div style="background:#1e293b;padding:50px 45px;border-radius:16px;
                  text-align:center;max-width:460px;width:90%;
                  border:2px solid #7f1d1d;box-shadow:0 30px 80px rgba(0,0,0,0.95);">
        <div style="font-size:64px;margin-bottom:16px;">🔐</div>
        <h2 style="color:#ef4444;font-size:24px;margin:0 0 14px;">Session Terminated</h2>
        <p style="color:#94a3b8;font-size:15px;line-height:1.6;margin:0 0 8px;">
          <strong>3 security violations</strong> were detected.<br>
          Your session has been forcibly terminated for your protection.
        </p>
        <p style="color:#475569;font-size:13px;margin:0 0 26px;">
          Reloading page in
          <span id="zt-countdown" style="color:#f59e0b;font-weight:bold;font-size:16px;">5</span>s…
        </p>
        <button id="zt-relog-btn"
          style="padding:13px 35px;border-radius:8px;border:none;
                 background:#38bdf8;color:#0f172a;font-weight:700;
                 cursor:pointer;font-size:15px;width:100%;">
          Login Again Now
        </button>
      </div>
    `;

    document.body.appendChild(overlay);
    document.body.style.overflow = 'hidden';

    let secs = 5;
    const el  = overlay.querySelector('#zt-countdown');
    const tmr = setInterval(() => {
      secs--;
      if (el) el.textContent = secs;
      if (secs <= 0) { clearInterval(tmr); window.location.reload(); }
    }, 1000);

    overlay.querySelector('#zt-relog-btn').addEventListener('click', () => {
      clearInterval(tmr);
      window.location.reload();
    });
  }

  // ── TELEMETRY FLUSH ───────────────────────────────────────
  async flush() {
    if (this.isLockedDown) return;

    const { keystrokes, mouse_movements, clicks, scrolls } = this.buffer;
    if (!keystrokes.length && !mouse_movements.length && !clicks.length && !scrolls.length) return;

    const currentBuffer   = {
      keystrokes:       [...keystrokes],
      mouse_movements:  [...mouse_movements],
      clicks:           [...clicks],
      scrolls:          [...scrolls]
    };
    const contentFeatures = this.getContentFeatures();
    const allTs = [...keystrokes.map(k => k.t), ...mouse_movements.map(m => m.t)];

    const payload = {
      session_id:             this.sessionId,
      calibration_session_id: this.calibrationSessionId,   // links to trained model
      timestamp_start:        allTs.length ? Math.min(...allTs) : Date.now(),
      timestamp_end:          Date.now(),
      is_calibration:         this.isCalibrationMode || false,
      content_features:       contentFeatures,              // writing-style analysis
      device_context: {
        user_agent:        navigator.userAgent,
        screen_resolution: `${window.screen.width}x${window.screen.height}`,
        platform:          navigator.platform,
        is_touch_device:   ('ontouchstart' in window) || (navigator.maxTouchPoints > 0)
      },
      events: currentBuffer
    };

    this.resetBuffer();   // clear immediately so new events aren't lost

    try {
      chrome.runtime.sendMessage(
        { action: 'FLUSH_TELEMETRY', payload, apiKey: this.apiKey },
        (response) => {
          if (chrome.runtime.lastError) {
            console.error('[ZeroTrust] Runtime error:', chrome.runtime.lastError.message);
            return;
          }
          if (!response) { console.warn('[ZeroTrust] No response from service worker.'); return; }

          if (response.status === 'success') {
            const verdict = response.data;
            console.log(`[ZeroTrust] Verdict: ${verdict.security_action} | Risk: ${verdict.risk_score}`);

            // Lock the tab on any security action from the server
            if (verdict.security_action === 'require_mfa' || verdict.security_action === 'block') {
              this.triggerLockdown();
            }
          } else {
            console.error('[ZeroTrust] Service worker error:', response.error);
          }
        }
      );
    } catch (err) {
      console.error('[ZeroTrust] Failed to reach Background Worker:', err);
    }
  }
}

// ── GATEKEEPER ─────────────────────────────────────────────
// Only activate after the user has completed calibration
chrome.storage.local.get(['isCalibrated'], (result) => {
  if (result.isCalibrated) {
    console.log('🛡️ Zero Trust Enterprise Shield: Calibrated and Active.');
    new BehaviorTracker('sk_live_51Mabcde12345');
  } else {
    console.log('⚠️ Zero Trust: Calibration pending. Tracker paused.');
  }
});