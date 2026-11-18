/**
 * PARTICLE SYSTEM  |  js/core/particles.js
 * Canvas-based animated particle network.
 * Reacts to --glow-intensity CSS var for adaptive density.
 */

export class ParticleSystem {
  /** @param {HTMLCanvasElement} canvas */
  constructor(canvas) {
    this.canvas  = canvas;
    this.ctx     = canvas.getContext('2d');
    this.particles = [];
    this.W = 0;
    this.H = 0;
    this._rafId = null;
    this._onResize = this._resize.bind(this);
  }

  init() {
    window.addEventListener('resize', this._onResize);
    this._resize();
    this._spawn(100);
    this._loop();
    return this;
  }

  destroy() {
    window.removeEventListener('resize', this._onResize);
    cancelAnimationFrame(this._rafId);
  }

  _resize() {
    this.W = this.canvas.width  = window.innerWidth;
    this.H = this.canvas.height = window.innerHeight;
  }

  _spawn(count) {
    for (let i = 0; i < count; i++) {
      this.particles.push(this._newParticle());
    }
  }

  _newParticle() {
    const { W, H } = this;
    return {
      x:    Math.random() * W,
      y:    Math.random() * H,
      r:    Math.random() * 1.4 + 0.3,
      vx:   (Math.random() - 0.5) * 0.28,
      vy:   (Math.random() - 0.5) * 0.28,
      life: Math.random(),            // phase offset
      maxLife: 0.5 + Math.random() * 0.5,
      hue:  Math.random() > 0.55 ? 210 : 195,
    };
  }

  _update(p) {
    p.x += p.vx;
    p.y += p.vy;
    p.life += 0.003;

    if (p.life > p.maxLife ||
        p.x < 0 || p.x > this.W ||
        p.y < 0 || p.y > this.H) {
      Object.assign(p, this._newParticle());
    }
  }

  _drawConnections() {
    const { ctx, particles } = this;
    for (let i = 0; i < particles.length; i++) {
      for (let j = i + 1; j < particles.length; j++) {
        const dx   = particles[i].x - particles[j].x;
        const dy   = particles[i].y - particles[j].y;
        const dist = Math.hypot(dx, dy);
        if (dist < 110) {
          const alpha = (1 - dist / 110) * 0.09;
          ctx.beginPath();
          ctx.moveTo(particles[i].x, particles[i].y);
          ctx.lineTo(particles[j].x, particles[j].y);
          ctx.strokeStyle = `rgba(0, 180, 255, ${alpha})`;
          ctx.lineWidth = 0.5;
          ctx.stroke();
        }
      }
    }
  }

  _loop() {
    const { ctx, W, H } = this;
    ctx.clearRect(0, 0, W, H);

    this._drawConnections();

    for (const p of this.particles) {
      this._update(p);
      const alpha = Math.sin((p.life / p.maxLife) * Math.PI) * 0.5;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      ctx.fillStyle = `hsla(${p.hue}, 100%, 70%, ${alpha})`;
      ctx.fill();
    }

    this._rafId = requestAnimationFrame(this._loop.bind(this));
  }
}
