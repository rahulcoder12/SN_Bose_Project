/**
 * CLIPBOARD  |  js/components/clipboard.js
 * Copy-to-clipboard for code blocks.
 * Falls back to execCommand for older browsers.
 */

export class ClipboardManager {
  init() {
    document.querySelectorAll('.copy-btn').forEach(btn => {
      btn.addEventListener('click', () => this._copy(btn));
    });
    return this;
  }

  async _copy(btn) {
    const text = btn.dataset.code || '';
    try {
      await navigator.clipboard.writeText(text);
      this._feedback(btn, 'Copied!', true);
    } catch {
      // Fallback
      this._fallbackCopy(text);
      this._feedback(btn, 'Copied!', true);
    }
  }

  _fallbackCopy(text) {
    const ta = Object.assign(document.createElement('textarea'), {
      value: text,
      style: 'position:fixed;opacity:0;',
    });
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    try { document.execCommand('copy'); } catch { /* silent fail */ }
    document.body.removeChild(ta);
  }

  _feedback(btn, msg, success) {
    const original = btn.textContent;
    btn.textContent = msg;
    btn.classList.toggle('copied', success);
    setTimeout(() => {
      btn.textContent = 'Copy';
      btn.classList.remove('copied');
    }, 2000);
  }
}
