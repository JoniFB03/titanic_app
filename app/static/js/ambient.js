/* =====================================================================
   ambient.js — the living ocean shared by every page.
   Sky (stars, aurora, shooting stars) · layered night sea · iceberg that
   peeks · foam cursor trail · click ripples · ship's-wheel menu · giant
   wave between pages · easter eggs ("iceberg", "sos", "mgy") · sound.
   Exposes window.Titanic for the page scripts.
   ===================================================================== */
(() => {
  "use strict";

  const root = document.documentElement;
  const motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
  const T = (window.Titanic = { reduced: motionQuery.matches });
  motionQuery.addEventListener?.("change", (e) => { T.reduced = e.matches; drawWorld(performance.now()); });

  /* ---------------------------------------------------------------- storage (never trusted to exist) */
  T.store = {
    get(key, fallback) {
      try { const v = sessionStorage.getItem(key); return v == null ? fallback : JSON.parse(v); } catch { return fallback; }
    },
    set(key, value) { try { sessionStorage.setItem(key, JSON.stringify(value)); } catch { /* private mode */ } },
  };
  const prefs = {
    get(key, fallback) { try { const v = localStorage.getItem(key); return v == null ? fallback : JSON.parse(v); } catch { return fallback; } },
    set(key, value) { try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* ignore */ } },
  };

  /* ---------------------------------------------------------------- toast */
  const toastEl = document.querySelector(".toast");
  let toastTimer;
  T.toast = (msg, ms = 3200) => {
    if (!toastEl) return;
    toastEl.textContent = msg;
    toastEl.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toastEl.classList.remove("show"), ms);
  };

  /* ---------------------------------------------------------------- sound (synthesised, muted by default) */
  let audio = null;
  const sound = (T.sound = {
    on: prefs.get("titanic.sound", false),
    ctx() {
      if (!this.on) return null;
      audio ??= new (window.AudioContext || window.webkitAudioContext)();
      if (audio.state === "suspended") audio.resume();
      return audio;
    },
    toggle() {
      this.on = !this.on;
      prefs.set("titanic.sound", this.on);
      if (this.on) this.horn(0.6);
      return this.on;
    },
    /** The ship's steam whistle: two detuned low saws through a lowpass. */
    horn(seconds = 1.6) {
      const ctx = this.ctx(); if (!ctx) return;
      const t = ctx.currentTime, gain = ctx.createGain(), filter = ctx.createBiquadFilter();
      filter.type = "lowpass"; filter.frequency.value = 520;
      gain.gain.setValueAtTime(0.0001, t);
      gain.gain.exponentialRampToValueAtTime(0.22, t + 0.12);
      gain.gain.setValueAtTime(0.22, t + seconds - 0.25);
      gain.gain.exponentialRampToValueAtTime(0.0001, t + seconds);
      for (const f of [92.5, 138.6, 69.3]) {
        const o = ctx.createOscillator(); o.type = "sawtooth"; o.frequency.value = f;
        o.connect(filter); o.start(t); o.stop(t + seconds + 0.05);
      }
      filter.connect(gain).connect(ctx.destination);
    },
    /** One Morse element (ms) at the classic 600-700 Hz sidetone. */
    beep(ms = 60, when = 0, freq = 660) {
      const ctx = this.ctx(); if (!ctx) return;
      const t = ctx.currentTime + when / 1000, o = ctx.createOscillator(), g = ctx.createGain();
      o.type = "sine"; o.frequency.value = freq;
      g.gain.setValueAtTime(0.0001, t);
      g.gain.exponentialRampToValueAtTime(0.12, t + 0.005);
      g.gain.setValueAtTime(0.12, t + ms / 1000 - 0.01);
      g.gain.exponentialRampToValueAtTime(0.0001, t + ms / 1000);
      o.connect(g).connect(ctx.destination); o.start(t); o.stop(t + ms / 1000 + 0.02);
    },
    morse(pattern, unit = 70) {
      let when = 0;
      for (const ch of pattern) {
        if (ch === ".") { this.beep(unit, when); when += unit * 2; }
        else if (ch === "-") { this.beep(unit * 3, when); when += unit * 4; }
        else when += unit * 3;
      }
    },
    /** Filtered noise: the whoosh of the giant wave. */
    whoosh(seconds = 1) {
      const ctx = this.ctx(); if (!ctx) return;
      const len = ctx.sampleRate * seconds, buf = ctx.createBuffer(1, len, ctx.sampleRate), data = buf.getChannelData(0);
      for (let i = 0; i < len; i++) data[i] = (Math.random() * 2 - 1) * Math.sin((Math.PI * i) / len);
      const src = ctx.createBufferSource(), f = ctx.createBiquadFilter(), g = ctx.createGain();
      src.buffer = buf; f.type = "lowpass"; f.frequency.setValueAtTime(300, ctx.currentTime);
      f.frequency.linearRampToValueAtTime(1800, ctx.currentTime + seconds * 0.6);
      g.gain.value = 0.35;
      src.connect(f).connect(g).connect(ctx.destination); src.start();
    },
  });

  const soundBtn = document.querySelector(".sound-toggle");
  const paintSound = () => {
    if (!soundBtn) return;
    soundBtn.setAttribute("aria-pressed", String(sound.on));
    soundBtn.querySelector(".label").textContent = sound.on ? "Sound on" : "Sound off";
  };
  soundBtn?.addEventListener("click", () => { sound.toggle(); paintSound(); });
  paintSound();

  /* ---------------------------------------------------------------- sky + sea canvases */
  const sky = document.getElementById("sky");
  const sea = document.getElementById("sea");
  const sctx = sky?.getContext("2d");
  const wctx = sea?.getContext("2d");
  let W = 0, H = 0, horizon = 0, dpr = 1, stars = [], glints = [], shooting = null, nextShooting = 4000;

  function horizonPx() {
    const raw = getComputedStyle(root).getPropertyValue("--horizon").trim();
    const n = parseFloat(raw);
    return raw.endsWith("vh") ? (n * window.innerHeight) / 100 : n || window.innerHeight * 0.64;
  }

  function resize() {
    if (!sky || !sea) return;
    dpr = Math.min(window.devicePixelRatio || 1, 1.6);
    W = window.innerWidth; H = window.innerHeight; horizon = horizonPx();
    for (const c of [sky, sea]) { c.width = Math.round(W * dpr); c.height = Math.round(H * dpr); }
    sctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    wctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const count = Math.min(420, Math.round((W * horizon) / 2600));
    stars = Array.from({ length: count }, () => ({
      x: Math.random() * W,
      y: Math.pow(Math.random(), 1.4) * (horizon - 8),
      r: Math.random() < 0.08 ? 1.5 + Math.random() : 0.4 + Math.random() * 0.9,
      p: Math.random() * Math.PI * 2,
      s: 0.6 + Math.random() * 2.2,
      warm: Math.random() < 0.15,
    }));
    glints = Array.from({ length: Math.round(W / 9) }, () => ({
      x: Math.random() * W,
      y: horizon + Math.pow(Math.random(), 2.2) * (H - horizon) * 0.7,
      p: Math.random() * Math.PI * 2,
      s: 1 + Math.random() * 3,
    }));
    drawWorld(performance.now());
  }

  function drawSky(t) {
    const g = sctx;
    g.clearRect(0, 0, W, H);
    // horizon haze
    const haze = g.createLinearGradient(0, horizon - 160, 0, horizon + 2);
    haze.addColorStop(0, "rgba(30,70,120,0)");
    haze.addColorStop(1, "rgba(60,110,160,.28)");
    g.fillStyle = haze; g.fillRect(0, horizon - 160, W, 162);

    // aurora: three luminous curtains breathing across the sky
    g.save();
    g.globalCompositeOperation = "lighter";
    const bands = [
      { y: 0.18, amp: 26, len: 0.0042, sp: 0.00011, c: [63, 224, 168], a: 0.11 },
      { y: 0.26, amp: 34, len: 0.0031, sp: -0.00008, c: [90, 160, 255], a: 0.08 },
      { y: 0.12, amp: 18, len: 0.0058, sp: 0.00015, c: [170, 110, 255], a: 0.05 },
    ];
    for (const b of bands) {
      const baseY = horizon * b.y;
      g.beginPath();
      for (let x = -20; x <= W + 20; x += 16) {
        const y = baseY + Math.sin(x * b.len + t * b.sp * 6) * b.amp + Math.sin(x * b.len * 2.3 - t * b.sp * 9) * b.amp * 0.4;
        x === -20 ? g.moveTo(x, y) : g.lineTo(x, y);
      }
      for (let x = W + 20; x >= -20; x -= 16) {
        const y = baseY + 120 + Math.sin(x * b.len * 1.3 + t * b.sp * 5) * b.amp * 0.7;
        g.lineTo(x, y);
      }
      g.closePath();
      const grad = g.createLinearGradient(0, baseY - b.amp, 0, baseY + 130);
      const pulse = b.a * (0.75 + 0.25 * Math.sin(t * 0.0004 + b.y * 10));
      grad.addColorStop(0, `rgba(${b.c},0)`);
      grad.addColorStop(0.25, `rgba(${b.c},${pulse})`);
      grad.addColorStop(1, `rgba(${b.c},0)`);
      g.fillStyle = grad;
      g.fill();
    }
    g.restore();

    // stars
    for (const s of stars) {
      const tw = T.reduced ? 0.8 : 0.55 + 0.45 * Math.sin(s.p + t * 0.001 * s.s);
      g.globalAlpha = tw;
      g.fillStyle = s.warm ? "#ffe6b0" : "#eaf3ff";
      g.beginPath(); g.arc(s.x, s.y, s.r, 0, Math.PI * 2); g.fill();
      if (s.r > 1.5) {
        g.globalAlpha = tw * 0.35;
        g.fillRect(s.x - s.r * 3, s.y - 0.4, s.r * 6, 0.8);
        g.fillRect(s.x - 0.4, s.y - s.r * 3, 0.8, s.r * 6);
      }
    }
    g.globalAlpha = 1;

    // the occasional shooting star
    if (!T.reduced) {
      if (!shooting && t > nextShooting) {
        shooting = { x: Math.random() * W * 0.8 + W * 0.2, y: Math.random() * horizon * 0.35, born: t };
        nextShooting = t + 9000 + Math.random() * 14000;
      }
      if (shooting) {
        const age = (t - shooting.born) / 900;
        if (age > 1) shooting = null;
        else {
          const x = shooting.x - age * 260, y = shooting.y + age * 110;
          const grad = g.createLinearGradient(x, y, x + 90, y - 38);
          grad.addColorStop(0, `rgba(255,255,255,${1 - age})`);
          grad.addColorStop(1, "rgba(255,255,255,0)");
          g.strokeStyle = grad; g.lineWidth = 1.6;
          g.beginPath(); g.moveTo(x, y); g.lineTo(x + 90, y - 38); g.stroke();
        }
      }
    }
  }

  const layers = [
    { f: 0.0, amp: 1.5, len: 0.05, sp: 0.0006, top: "#1d4677", fill: "#0f2a4c" },
    { f: 0.07, amp: 3, len: 0.03, sp: -0.0008, top: "#1a416f", fill: "#0c2442" },
    { f: 0.18, amp: 6, len: 0.018, sp: 0.0009, top: "#173a64", fill: "#0a1f3a" },
    { f: 0.36, amp: 10, len: 0.011, sp: -0.0011, top: "#123156", fill: "#081a31" },
    { f: 0.6, amp: 16, len: 0.0075, sp: 0.0013, top: "#0f2a4a", fill: "#061428" },
  ];

  function drawSea(t) {
    const g = wctx;
    g.clearRect(0, 0, W, H);
    const depth = H - horizon;
    for (const L of layers) {
      const base = horizon + depth * L.f;
      const motion = T.reduced ? 0 : t * L.sp;
      g.beginPath();
      g.moveTo(0, H);
      for (let x = 0; x <= W + 12; x += 12) {
        const y = base + Math.sin(x * L.len + motion) * L.amp + Math.sin(x * L.len * 2.7 - motion * 1.4) * L.amp * 0.35;
        g.lineTo(x, y);
      }
      g.lineTo(W, H);
      g.closePath();
      const grad = g.createLinearGradient(0, base - L.amp, 0, H);
      grad.addColorStop(0, L.top);
      grad.addColorStop(0.25, L.fill);
      grad.addColorStop(1, "#030b18");
      g.fillStyle = grad;
      g.fill();
      g.strokeStyle = "rgba(170,210,255,.12)";
      g.lineWidth = 1;
      g.stroke();
    }
    // starlight glints on the swell
    for (const s of glints) {
      const a = T.reduced ? 0.25 : Math.max(0, Math.sin(s.p + t * 0.0012 * s.s));
      if (a < 0.05) continue;
      g.globalAlpha = a * 0.6;
      g.fillStyle = "#cfe6ff";
      g.fillRect(s.x, s.y, 2 + a * 4, 1);
    }
    g.globalAlpha = 1;
  }

  function drawWorld(t) {
    if (!sctx || !wctx || !W) return;
    drawSky(t);
    drawSea(t);
  }

  let rafId = 0;
  function loop(t) {
    drawWorld(t);
    rafId = T.reduced || document.hidden ? 0 : requestAnimationFrame(loop);
  }
  function start() { if (!rafId && !T.reduced && !document.hidden) rafId = requestAnimationFrame(loop); }
  document.addEventListener("visibilitychange", start);
  motionQuery.addEventListener?.("change", start);
  let resizeTimer;
  window.addEventListener("resize", () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(resize, 120); });
  resize();
  start();

  /* ---------------------------------------------------------------- the iceberg that peeks */
  const berg = document.querySelector(".iceberg-peek");
  T.peekIceberg = (ms = 7000) => {
    if (!berg) return;
    berg.classList.add("peek");
    clearTimeout(berg._t);
    berg._t = setTimeout(() => berg.classList.remove("peek"), ms);
  };
  (function schedulePeek(first) {
    setTimeout(() => { T.peekIceberg(); schedulePeek(false); }, first ? 7000 : 22000 + Math.random() * 26000);
  })(true);

  /* ---------------------------------------------------------------- foam cursor trail */
  const foam = document.getElementById("foam");
  const fctx = foam?.getContext("2d");
  const bubbles = [];
  let foamRaf = 0;
  function sizeFoam() {
    if (!foam) return;
    foam.width = Math.round(window.innerWidth * dpr); foam.height = Math.round(window.innerHeight * dpr);
    fctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  sizeFoam();
  window.addEventListener("resize", sizeFoam);

  function foamLoop() {
    fctx.clearRect(0, 0, foam.width, foam.height);
    const now = performance.now();
    for (let i = bubbles.length - 1; i >= 0; i--) {
      const b = bubbles[i];
      const age = (now - b.born) / b.life;
      if (age >= 1) { bubbles.splice(i, 1); continue; }
      b.x += b.vx; b.y += b.vy; b.vy -= 0.02; b.vx *= 0.98;
      const r = b.r * (0.6 + age * 0.8);
      fctx.globalAlpha = (1 - age) * 0.85;
      fctx.beginPath(); fctx.arc(b.x, b.y, r, 0, Math.PI * 2);
      fctx.fillStyle = "rgba(240,250,255,.55)"; fctx.fill();
      fctx.lineWidth = 1; fctx.strokeStyle = "rgba(140,200,240,.9)"; fctx.stroke();
      fctx.beginPath(); fctx.arc(b.x - r * 0.35, b.y - r * 0.35, r * 0.25, 0, Math.PI * 2);
      fctx.fillStyle = "#fff"; fctx.fill();
    }
    fctx.globalAlpha = 1;
    foamRaf = bubbles.length ? requestAnimationFrame(foamLoop) : 0;
  }
  let lastFoam = 0;
  window.addEventListener("pointermove", (e) => {
    if (T.reduced || !fctx) return;
    const now = performance.now();
    if (now - lastFoam < 16) return;
    lastFoam = now;
    const n = e.pointerType === "touch" ? 1 : 2;
    for (let i = 0; i < n && bubbles.length < 160; i++) {
      bubbles.push({
        x: e.clientX + (Math.random() - 0.5) * 10, y: e.clientY + (Math.random() - 0.5) * 10,
        vx: (Math.random() - 0.5) * 1.2, vy: Math.random() * 0.6,
        r: 1.5 + Math.random() * 4.5, born: now, life: 600 + Math.random() * 700,
      });
    }
    if (!foamRaf) foamRaf = requestAnimationFrame(foamLoop);
  }, { passive: true });

  /* ---------------------------------------------------------------- ripples on click */
  T.ripple = (x, y) => {
    if (T.reduced) return;
    for (const cls of ["r1", "r2", "r3"]) {
      const r = document.createElement("span");
      r.className = `ripple ${cls}`;
      r.style.left = `${x}px`; r.style.top = `${y}px`;
      document.body.appendChild(r);
      r.addEventListener("animationend", () => r.remove(), { once: true });
      setTimeout(() => r.remove(), 1600);
    }
  };
  window.addEventListener("pointerdown", (e) => T.ripple(e.clientX, e.clientY), { passive: true });

  /* ---------------------------------------------------------------- ship's wheel menu */
  const helm = document.querySelector(".helm");
  const wheel = helm?.querySelector(".wheel");
  const setHelm = (open) => {
    helm.classList.toggle("open", open);
    wheel.setAttribute("aria-expanded", String(open));
    if (open) sound.beep(40, 0, 880);
  };
  wheel?.addEventListener("click", () => setHelm(!helm.classList.contains("open")));
  document.addEventListener("click", (e) => { if (helm && !helm.contains(e.target)) setHelm(false); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && helm?.classList.contains("open")) { setHelm(false); wheel.focus(); } });

  /* ---------------------------------------------------------------- the giant wave between pages */
  document.addEventListener("click", (e) => {
    const a = e.target.closest("a[data-wave]");
    if (!a || e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    const url = new URL(a.href, location.href);
    if (url.origin !== location.origin) return;
    e.preventDefault();
    if (url.pathname === location.pathname) { setHelm(false); return; }
    T.store.set("titanic.wave", 1);
    if (T.reduced) { location.href = url.href; return; }
    sound.whoosh(1.1);
    root.classList.add("surging");
    setTimeout(() => { location.href = url.href; }, 820);
  });
  if (root.classList.contains("arriving")) {
    try { sessionStorage.removeItem("titanic.wave"); } catch { /* ignore */ }
    requestAnimationFrame(() => requestAnimationFrame(() => root.classList.add("receding")));
    setTimeout(() => root.classList.remove("arriving", "receding"), 1300);
  }
  window.addEventListener("pageshow", (e) => { if (e.persisted) root.classList.remove("surging", "arriving", "receding"); });

  /* ---------------------------------------------------------------- easter eggs */
  T.iceberg = () => {
    root.classList.remove("shake"); void root.offsetWidth; root.classList.add("shake");
    setTimeout(() => root.classList.remove("shake"), 1000);
    T.peekIceberg(9000);
    T.toast("ICEBERG RIGHT AHEAD STOP HARD A-STARBOARD STOP", 3600);
    sound.horn(1.4);
    navigator.vibrate?.([120, 60, 200]);
  };
  let typed = "";
  document.addEventListener("keydown", (e) => {
    if (e.key.length !== 1) return;
    typed = (typed + e.key.toLowerCase()).slice(-12);
    if (typed.endsWith("iceberg")) { typed = ""; T.iceberg(); }
    else if (typed.endsWith("sos")) {
      typed = "";
      root.classList.remove("sos"); void root.offsetWidth; root.classList.add("sos");
      setTimeout(() => root.classList.remove("sos"), 3700);
      sound.morse("... --- ...");
      T.toast("··· ——— ··· SOS SOS SOS STOP", 3600);
    } else if (typed.endsWith("mgy")) {
      typed = "";
      T.toast("MGY STOP THAT IS OUR CALL SIGN STOP YOU KNOW YOUR WIRELESS STOP");
      sound.morse("-- --. -.--");
    }
  });
})();
