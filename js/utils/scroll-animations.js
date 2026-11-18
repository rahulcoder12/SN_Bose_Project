/**
 * SCROLL ANIMATIONS  |  js/utils/scroll-animations.js
 * IntersectionObserver-based scroll-reveal utility.
 * Elements receive the .visible class when entering the viewport.
 * Supports staggered delays via data-delay attribute.
 */

export class ScrollAnimator {
  /**
   * @param {string[]} selectors  CSS selectors of elements to animate
   * @param {{ threshold?: number, rootMargin?: string }} options
   */
  constructor(
    selectors = ['.feature-card', '.step', '.download-card', '.sec-item', '.security-card'],
    options   = {}
  ) {
    this.selectors = selectors;
    this.threshold  = options.threshold  ?? 0.12;
    this.rootMargin = options.rootMargin ?? '0px 0px -40px 0px';
    this._observer  = null;
  }

  init() {
    this._observer = new IntersectionObserver(
      (entries) => entries.forEach(e => {
        if (e.isIntersecting) {
          e.target.classList.add('visible');
          this._observer.unobserve(e.target);
        }
      }),
      { threshold: this.threshold, rootMargin: this.rootMargin }
    );

    let globalIndex = 0;
    this.selectors.forEach(sel => {
      document.querySelectorAll(sel).forEach((el) => {
        // Assign stagger delay if not already set
        if (!el.dataset.delay) {
          el.dataset.delay = String((globalIndex % 6) + 1);
          globalIndex++;
        }

        // Make sure the element has a CSS transition with the delay
        const delayMs = (parseInt(el.dataset.delay, 10) - 1) * 80;
        el.style.transitionDelay = `${delayMs}ms`;

        this._observer.observe(el);
      });
    });

    return this;
  }

  destroy() {
    this._observer?.disconnect();
  }
}

/* ─── TYPING ANIMATION (hero badge text) ───────────────────────── */
export class TypingAnimation {
  /**
   * @param {Element} container  Element whose last text node will be animated
   * @param {string[]} texts     Array of strings to cycle through
   */
  constructor(container, texts = []) {
    this.container = container;
    this.texts     = texts;
    this.index     = 0;
    this._timerId  = null;
  }

  init(delay = 800) {
    if (!this.container || this.texts.length === 0) return this;
    // Ensure last child is a text node
    if (this.container.lastChild?.nodeType !== Node.TEXT_NODE) {
      this.container.appendChild(document.createTextNode(''));
    }
    this._timerId = setTimeout(() => this._typeText(this.texts[0]), delay);
    return this;
  }

  _getTextNode() {
    return this.container.lastChild;
  }

  _typeText(text, i = 0) {
    this._getTextNode().textContent = ' ' + text.slice(0, i);
    if (i <= text.length) {
      this._timerId = setTimeout(() => this._typeText(text, i + 1), 60);
    } else {
      this._timerId = setTimeout(() => this._eraseText(text), 2800);
    }
  }

  _eraseText(text) {
    let i = text.length;
    const step = () => {
      this._getTextNode().textContent = ' ' + text.slice(0, i);
      if (i-- >= 0) {
        this._timerId = setTimeout(step, 36);
      } else {
        this.index = (this.index + 1) % this.texts.length;
        this._timerId = setTimeout(() => this._typeText(this.texts[this.index]), 400);
      }
    };
    step();
  }

  destroy() { clearTimeout(this._timerId); }
}
