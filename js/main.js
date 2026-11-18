/**
 * MAIN ENTRY POINT  |  js/main.js
 * Imports and initialises all modules.
 * Each module is independent and can be tree-shaken in a bundler.
 */

import { ParticleSystem    } from './core/particles.js';
import { ThemeManager      } from './core/theme.js';
import { NavbarController  } from './components/navbar.js';
import { TabManager        } from './components/tabs.js';
import { ClipboardManager  } from './components/clipboard.js';
import { CounterAnimator   } from './utils/counter.js';
import { ParallaxEffect    } from './utils/parallax.js';
import { ScrollAnimator, TypingAnimation } from './utils/scroll-animations.js';

/* ── Boot sequence ─────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {

  /* 1. Particles — canvas background */
  const canvas = document.getElementById('particles-canvas');
  if (canvas) new ParticleSystem(canvas).init();

  /* 2. Theme — dynamic CSS vars + theme switcher */
  new ThemeManager().init();

  /* 3. Navbar — scroll state, hamburger, smooth-scroll, active links */
  new NavbarController().init();

  /* 4. Tab panels — API docs */
  new TabManager('.docs-nav', 'panel-').init();

  /* 5. Clipboard — code block copy buttons */
  new ClipboardManager().init();

  /* 6. Animated counters — stat numbers in hero */
  new CounterAnimator().init();

  /* 7. Mouse parallax — hero glow layers */
  new ParallaxEffect('.hero-glow', 28).init();

  /* 8. Scroll reveal — cards, steps, sec-items */
  new ScrollAnimator([
    '.feature-card',
    '.step',
    '.download-card',
    '.sec-item',
    '.security-card',
  ]).init();

  /* 9. Typing animation — hero badge label */
  const heroBadge = document.querySelector('.hero-badge');
  if (heroBadge) {
    new TypingAnimation(heroBadge, [
      'Enterprise-Grade AI Security',
      'Zero Friction Authentication',
      'Behavioral Biometrics',
      'Continuous Identity Verification',
      'Isolation Forest AI Engine',
    ]).init(900);
  }

  /* 10. Button ripple effect (delegated) */
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('.btn');
    if (!btn) return;
    const rect = btn.getBoundingClientRect();
    const ripple = Object.assign(document.createElement('span'), {
      className: 'ripple',
    });
    ripple.style.cssText = `
      width: 10px; height: 10px;
      left: ${e.clientX - rect.left}px;
      top:  ${e.clientY - rect.top}px;
    `;
    btn.appendChild(ripple);
    ripple.addEventListener('animationend', () => ripple.remove());
  });

  /* 11. Live security score — pulse the score display */
  const scoreEl = document.querySelector('.sc-score');
  if (scoreEl) {
    setInterval(() => {
      const score = (93.5 + Math.random() * 5.5).toFixed(1);
      scoreEl.textContent = score + '%';
    }, 3500);
  }

  /* Dev log */
  console.log(
    '%c🛡 Zero Trust Auth%c v1.0 | Loaded',
    'font-size:14px;font-weight:700;color:#00d4ff;',
    'font-size:14px;color:#8899bb;'
  );
});
