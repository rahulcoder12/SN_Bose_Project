/**
 * TABS COMPONENT  |  js/components/tabs.js
 * Accessible tab panel switching for the API docs section.
 */

export class TabManager {
  /** @param {string} navSelector  @param {string} panelPrefix */
  constructor(navSelector = '.docs-nav', panelPrefix = 'panel-') {
    this.nav         = document.querySelector(navSelector);
    this.panelPrefix = panelPrefix;
    this.tabs        = [];
    this.panels      = [];
  }

  init() {
    if (!this.nav) return this;
    this.tabs   = Array.from(this.nav.querySelectorAll('.docs-tab'));
    this.panels = this.tabs.map(t =>
      document.getElementById(this.panelPrefix + t.dataset.panel)
    ).filter(Boolean);

    this.tabs.forEach((tab, i) => {
      tab.addEventListener('click', () => this.show(i));
      // Keyboard nav
      tab.addEventListener('keydown', (e) => {
        if (e.key === 'ArrowRight') this.show((i + 1) % this.tabs.length);
        if (e.key === 'ArrowLeft')  this.show((i - 1 + this.tabs.length) % this.tabs.length);
      });
    });

    this.show(0);
    return this;
  }

  show(index) {
    this.tabs.forEach((tab, i) => {
      const active = i === index;
      tab.classList.toggle('active', active);
      tab.setAttribute('aria-selected', String(active));
      tab.tabIndex = active ? 0 : -1;
    });

    this.panels.forEach((panel, i) => {
      if (i === index) {
        panel.removeAttribute('hidden');
        // Fade-in effect
        panel.style.animation = 'none';
        panel.offsetHeight;   // reflow
        panel.style.animation = 'fade-in 0.3s ease';
      } else {
        panel.setAttribute('hidden', '');
      }
    });
  }
}
