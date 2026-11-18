/**
 * NAVBAR CONTROLLER  |  js/components/navbar.js
 * Handles: scroll state, hamburger toggle, active link highlighting,
 * smooth-scroll for anchor links, ripple on mobile links.
 */

export class NavbarController {
  constructor() {
    this.nav       = document.getElementById('navbar');
    this.hamburger = document.getElementById('hamburger');
    this.navLinks  = document.getElementById('nav-links');
    this.sections  = [];
    this.allLinks  = [];
  }

  init() {
    this._bindScroll();
    this._bindHamburger();
    this._bindSmoothScroll();
    this._collectSections();
    return this;
  }

  /* ── SCROLL STATE ──────────────────────────────────────────── */
  _bindScroll() {
    const onScroll = () => {
      this.nav.classList.toggle('scrolled', window.scrollY > 30);
      this._highlightActiveSection();
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll(); // run once on load
  }

  /* ── HAMBURGER ─────────────────────────────────────────────── */
  _bindHamburger() {
    this.hamburger?.addEventListener('click', () => {
      const isOpen = this.navLinks.classList.toggle('open');
      this.hamburger.classList.toggle('open', isOpen);
      this.hamburger.setAttribute('aria-expanded', String(isOpen));
    });

    // Close on outside click
    document.addEventListener('click', (e) => {
      if (!this.nav.contains(e.target)) {
        this.navLinks.classList.remove('open');
        this.hamburger?.classList.remove('open');
      }
    });
  }

  /* ── SMOOTH SCROLL ─────────────────────────────────────────── */
  _bindSmoothScroll() {
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
      anchor.addEventListener('click', (e) => {
        const target = document.querySelector(anchor.getAttribute('href'));
        if (!target) return;
        e.preventDefault();
        // Close mobile menu
        this.navLinks.classList.remove('open');
        this.hamburger?.classList.remove('open');
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    });
  }

  /* ── ACTIVE SECTION HIGHLIGHT ──────────────────────────────── */
  _collectSections() {
    this.allLinks = Array.from(document.querySelectorAll('.nav-link[href^="#"]'));
    this.sections = this.allLinks
      .map(link => document.querySelector(link.getAttribute('href')))
      .filter(Boolean);
  }

  _highlightActiveSection() {
    const scrollY = window.scrollY + 100;
    let current = null;

    for (const section of this.sections) {
      if (section.offsetTop <= scrollY) current = section;
    }

    this.allLinks.forEach(link => {
      const href = link.getAttribute('href').slice(1);
      link.classList.toggle('active', current?.id === href);
    });
  }
}
