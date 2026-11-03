/* Presentation tweening for INDICATOR values.
   - Only animates the transition between two RECEIVED samples; the final displayed value
     is always the real sample value.
   - The raw measured value is always kept in dataset.raw and shown as a tooltip, so the
     animation can never hide what the board actually reported.
   - Can be switched off entirely (window.SMOOTH_VALUES=false) for strict evidence review. */
(() => {
  'use strict';
  const store = new WeakMap();
  const raf = window.requestAnimationFrame.bind(window);
  const ease = t => 1 - Math.pow(1 - t, 3);
  const enabled = () => window.SMOOTH_VALUES !== false && !window.measurementReplayActive;

  function finish(el, s, format) {
    s.current = s.to;
    s.running = false;
    el.textContent = format(s.to);
    el.classList.remove('value-changing');
  }

  function step(el, s, format) {
    if (store.get(el) !== s) return; // A new context or plain assignment cancels old animation.
    if (!enabled()) { finish(el, s, format); return; }
    const t = s.duration > 0 ? Math.min(1, (performance.now() - s.start) / s.duration) : 1;
    s.current = s.from + (s.to - s.from) * ease(t);
    el.textContent = format(s.current);
    if (t < 1) raf(() => step(el, s, format));
    else finish(el, s, format);
  }

  /* Set an element's text to value using format(); animate the change when a previous
     real sample exists. Non-numeric targets are written verbatim. */
  window.setSmooth = function (el, value, format, duration) {
    if (!el) return;
    const fmt = format || (x => String(x ?? '—'));
    const numeric = value !== null && value !== undefined && Number.isFinite(Number(value));
    if (!numeric) { store.delete(el); el.textContent = fmt(value); el.removeAttribute('title'); return; }
    const target = Number(value);
    el.dataset.raw = String(target);
    el.title = '实测值 ' + fmt(target);
    let s = store.get(el);
    if (!s) {
      s = { current: target, from: target, to: target, start: 0, duration: 0, running: false };
      store.set(el, s);
      el.textContent = fmt(target);
      return;
    }
    if (!enabled()) { store.delete(el); el.textContent = fmt(target); return; }
    if (Math.abs(s.to - target) < 1e-12) return;
    s.from = s.current;
    s.to = target;
    s.start = performance.now();
    s.duration = Math.max(120, Math.min(1500, duration || 520));
    el.classList.add('value-changing');
    if (!s.running) { s.running = true; raf(() => step(el, s, fmt)); }
  };

  /* Plain assignment, used where animation would be misleading (labels, ids, states). */
  window.setPlain = function (el, text) {
    if (!el) return;
    store.delete(el);
    el.textContent = text;
    el.removeAttribute('title');
    delete el.dataset.raw;
  };

  /* Same idea for element properties such as <progress>.value. */
  const pstore = new WeakMap();
  window.setSmoothValue = function (el, value, duration) {
    if (!el) return;
    if (!Number.isFinite(Number(value))) { pstore.delete(el); el.value = 0; return; }
    const target = Number(value);
    let s = pstore.get(el);
    if (!s) { s = { current: target }; pstore.set(el, s); el.value = target; return; }
    if (!enabled()) { pstore.delete(el); el.value = target; return; }
    if (Math.abs(s.current - target) < 1e-9) return;
    const token = s.token = (s.token || 0) + 1;
    const from = s.current, start = performance.now(), dur = Math.max(120, Math.min(1500, duration || 520));
    const tick = () => {
      if (pstore.get(el) !== s || s.token !== token) return;
      const t = Math.min(1, (performance.now() - start) / dur);
      s.current = from + (target - from) * ease(t);
      el.value = s.current;
      if (t < 1) raf(tick);
    };
    raf(tick);
  };

  window.smoothState = () => ({ enabled: enabled() });
})();
