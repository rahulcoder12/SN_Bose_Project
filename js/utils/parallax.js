/**
 * PARALLAX EFFECT  |  js/utils/parallax.js
 * Mouse-driven parallax for hero glow layers.
 * Reads --mouse-x / --mouse-y (set by theme.js) OR falls back
 * to direct mousemove for elements that need transform parallax.
 */

export class ParallaxEffect {
  /**
   * @param {string} selector  CSS selector for parallax elements
   * @param {number} intensity Max pixel displacement
   */
  constructor(selector = '.hero-glow', intensity = 30) {
    this.elements  = Array.from(document.querySelectorAll(selector));
    this.intensity = intensity;
    this._handler  = null;
  }

  init() {
    if (this.elements.length === 0) return this;

    this._handler = (e) => {
      const cx = (e.clientX / window.innerWidth  - 0.5) * 2; // -1 → 1
      const cy = (e.clientY / window.innerHeight - 0.5) * 2; // -1 → 1

      this.elements.forEach((el, i) => {
        const factor = (i + 1) * 0.35;
        const tx = cx * this.intensity * factor;
        const ty = cy * this.intensity * factor;
        el.style.transform = `translate(${tx}px, ${ty}px)`;
      });
    };

    window.addEventListener('mousemove', this._handler, { passive: true });
    return this;
  }

  destroy() {
    if (this._handler) {
      window.removeEventListener('mousemove', this._handler);
    }
  }
}
