/**
 * ANIMATED COUNTER  |  js/utils/counter.js
 * Animates numeric text nodes when they scroll into view.
 * Supports integer and decimal (one decimal place) values.
 */

export class CounterAnimator {
  constructor() {
    this._observer = null;
  }

  init() {
    this._observer = new IntersectionObserver(
      (entries) => entries.forEach(e => {
        if (e.isIntersecting) {
          this._animate(e.target);
          this._observer.unobserve(e.target);
        }
      }),
      { threshold: 0.6 }
    );

    document.querySelectorAll('.stat-number').forEach(el => {
      this._observer.observe(el);
    });

    return this;
  }

  _animate(el) {
    const raw     = el.textContent.trim();
    const number  = parseFloat(raw.replace(/[^\d.]/g, ''));
    const prefix  = raw.match(/^[^\d]*/)?.[0] ?? '';
    const suffix  = raw.match(/[^\d.]*$/)?.[0] ?? '';
    const isFloat = raw.includes('.');

    if (isNaN(number) || number === 0) return;

    const duration = 1600;
    const start    = performance.now();

    const tick = (now) => {
      const elapsed  = now - start;
      const progress = Math.min(elapsed / duration, 1);
      const eased    = 1 - Math.pow(1 - progress, 3); // cubic ease-out
      const value    = number * eased;

      el.textContent = prefix + (isFloat
        ? value.toFixed(1)
        : Math.floor(value).toString()
      ) + suffix;

      if (progress < 1) requestAnimationFrame(tick);
    };

    requestAnimationFrame(tick);
  }
}
