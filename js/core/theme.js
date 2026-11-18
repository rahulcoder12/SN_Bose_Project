/**
 * THEME MANAGER  |  js/core/theme.js
 * Manages three themes (cyber, space, emerald) via data-theme on <html>.
 * Also drives dynamic CSS custom properties in real-time:
 *   --scroll-ratio   (0→1)
 *   --mouse-x / --mouse-y  (0→1 normalized)
 *   --glow-intensity  (pulses with scroll position)
 */

const THEMES = ['cyber', 'space', 'emerald'];
const STORAGE_KEY = 'zt-theme';

export class ThemeManager {
  constructor() {
    this.root    = document.documentElement;
    this.current = localStorage.getItem(STORAGE_KEY) || 'cyber';
    this._rafPending = false;
    this._scrollY   = 0;
    this._mouseX    = 0.5;
    this._mouseY    = 0.5;
  }

  init() {
    this._applyTheme(this.current);
    this._bindScrollTick();
    this._bindMouseMove();
    this._bindThemeButtons();
    return this;
  }

  /* ── THEME APPLICATION ─────────────────────────────────────── */
  _applyTheme(name) {
    this.current = name;
    // Clear previous data-theme
    THEMES.forEach(t => this.root.removeAttribute('data-theme'));
    if (name !== 'cyber') this.root.setAttribute('data-theme', name);
    localStorage.setItem(STORAGE_KEY, name);

    // Highlight active button
    document.querySelectorAll('.theme-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.theme === name);
    });
  }

  cycleTheme() {
    const idx  = THEMES.indexOf(this.current);
    const next = THEMES[(idx + 1) % THEMES.length];
    this._applyTheme(next);
  }

  /* ── SCROLL-DRIVEN CSS VARS ────────────────────────────────── */
  _bindScrollTick() {
    window.addEventListener('scroll', () => {
      this._scrollY = window.scrollY;
      if (!this._rafPending) {
        this._rafPending = true;
        requestAnimationFrame(() => {
          this._updateScrollVars();
          this._rafPending = false;
        });
      }
    }, { passive: true });
  }

  _updateScrollVars() {
    const maxScroll = document.documentElement.scrollHeight - window.innerHeight;
    const ratio     = maxScroll > 0 ? Math.min(this._scrollY / maxScroll, 1) : 0;

    // Glow intensity: higher near hero (top) and final CTA (bottom)
    const glowIntensity = 1 + Math.sin(ratio * Math.PI) * 0.6;

    this.root.style.setProperty('--scroll-ratio',    ratio.toFixed(4));
    this.root.style.setProperty('--glow-intensity',  glowIntensity.toFixed(3));
  }

  /* ── MOUSE-PARALLAX CSS VARS ───────────────────────────────── */
  _bindMouseMove() {
    window.addEventListener('mousemove', (e) => {
      this._mouseX = (e.clientX / window.innerWidth).toFixed(4);
      this._mouseY = (e.clientY / window.innerHeight).toFixed(4);
      this.root.style.setProperty('--mouse-x', this._mouseX);
      this.root.style.setProperty('--mouse-y', this._mouseY);
    }, { passive: true });
  }

  /* ── THEME BUTTONS ─────────────────────────────────────────── */
  _bindThemeButtons() {
    document.querySelectorAll('.theme-btn').forEach(btn => {
      btn.addEventListener('click', () => this._applyTheme(btn.dataset.theme));
    });
  }
}
