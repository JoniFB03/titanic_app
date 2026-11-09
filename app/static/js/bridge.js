/* bridge.js — regatta race, boarding ticket, brass gauge, effects, passenger chart, joke telegram. */
(() => {
  "use strict";
  const T = window.Titanic;
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const root = document.documentElement;
  const css = getComputedStyle(root);
  const color = (name) => css.getPropertyValue(name).trim();

  /* ================================================================ the regatta */
  const regatta = $(".regatta");
  const results = JSON.parse(regatta.dataset.results);
  const accs = results.map((r) => r.accuracy);
  const lo = Math.floor(Math.min(...accs) * 100 - 2) / 100;
  const hi = Math.ceil(Math.max(...accs) * 100 + 1) / 100;
  const toPos = (a) => Math.max(0, Math.min(1, (a - lo) / (hi - lo)));

  // Axis: one tick per percentage point, labelled every other one on narrow screens.
  const axis = $(".axis");
  const nTicks = Math.round((hi - lo) * 100);
  for (let k = 0; k <= nTicks; k++) {
    const v = lo + k / 100;
    const tick = document.createElement("div");
    tick.className = "tick";
    // the boat's bow is its right edge, so align ticks with where the bow ends up
    tick.style.left = `calc(${toPos(v)} * (100% - var(--boat-w, 110px)) + var(--boat-w, 110px))`;
    if (k % (window.innerWidth < 640 ? 2 : 1) === 0) tick.innerHTML = `<span>${Math.round(v * 100)}%</span>`;
    axis.appendChild(tick);
  }
  const syncBoatWidth = () => axis.style.setProperty("--boat-w", `${$(".boat").offsetWidth}px`);
  syncBoatWidth();
  window.addEventListener("resize", syncBoatWidth);

  function race() {
    regatta.classList.add("raced");
    $$(".lane").forEach((lane) => {
      const pos = toPos(parseFloat(lane.dataset.acc));
      const boat = $(".boat", lane);
      boat.style.setProperty("--i", lane.style.getPropertyValue("--i"));
      boat.style.setProperty("--pos", pos.toFixed(4));
      if (pos > 0.8) boat.classList.add("late-label");
    });
    setTimeout(() => {
      const winner = $(".lane.winner");
      winner?.classList.add("crowned");
      T.sound.horn(1.2);
      if (winner) fireworks($(".boat", winner));
    }, T.reduced ? 0 : 3700);
  }
  const io = new IntersectionObserver((entries) => {
    if (entries.some((e) => e.isIntersecting)) { io.disconnect(); setTimeout(race, T.reduced ? 0 : 350); }
  }, { threshold: 0.35 });
  io.observe(regatta);

  /** Fireworks over the regatta, bursting around the winning ship. */
  function fireworks(target) {
    if (T.reduced) return;
    const cvs = $(".fireworks");
    const box = regatta.getBoundingClientRect();
    const dpr = Math.min(window.devicePixelRatio || 1, 1.6);
    cvs.width = box.width * dpr; cvs.height = box.height * dpr;
    const g = cvs.getContext("2d");
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    const t = target.getBoundingClientRect();
    const cx = t.left - box.left + t.width / 2, cy = t.top - box.top - 30;
    const palette = ["#f5c542", "#fff4d0", "#e8735a", "#5ab4e6", "#d8a23a", "#ffffff"];
    const sparks = [];
    const burst = (x, y) => {
      const c = palette[(Math.random() * palette.length) | 0];
      for (let i = 0; i < 46; i++) {
        const a = (Math.PI * 2 * i) / 46, v = 1.6 + Math.random() * 2.4;
        sparks.push({ x, y, vx: Math.cos(a) * v, vy: Math.sin(a) * v, life: 1, c });
      }
      T.sound.beep(30, 0, 220 + Math.random() * 200);
    };
    let n = 0;
    const timer = setInterval(() => {
      burst(cx + (Math.random() - 0.5) * Math.min(box.width * 0.6, 420), Math.max(30, cy - Math.random() * 120));
      if (++n >= 7) clearInterval(timer);
    }, 260);
    const tick = () => {
      g.globalCompositeOperation = "destination-out";
      g.fillStyle = "rgba(0,0,0,.22)"; g.fillRect(0, 0, box.width, box.height);
      g.globalCompositeOperation = "lighter";
      for (const s of sparks) {
        if (s.life <= 0) continue;
        s.x += s.vx; s.y += s.vy; s.vy += 0.045; s.vx *= 0.985; s.life -= 0.012;
        g.globalAlpha = Math.max(0, s.life);
        g.fillStyle = s.c;
        g.beginPath(); g.arc(s.x, s.y, 2, 0, Math.PI * 2); g.fill();
      }
      g.globalAlpha = 1;
      if (sparks.some((s) => s.life > 0) || n < 7) requestAnimationFrame(tick);
      else g.clearRect(0, 0, box.width, box.height);
    };
    requestAnimationFrame(tick);
  }

  /* ================================================================ the boarding ticket */
  const form = $(".ticket");
  const fare = form.elements.fare;
  const ageOut = form.elements.age_out;
  let fareEdited = false;
  $(".ticket-no").textContent = `1912-${String(1000 + ((Math.random() * 8999) | 0))}`;

  const FEMALE = new Set(["Mrs", "Miss", "Lady", "Countess", "Mme", "Mlle", "Ms"]);
  const MALE = new Set(["Mr", "Master", "Sir", "Don", "Rev", "Col", "Major", "Capt"]);
  form.elements.title.addEventListener("change", (e) => {
    const t = e.target.value;
    const sex = FEMALE.has(t) ? "female" : MALE.has(t) ? "male" : null;
    if (sex) form.querySelector(`input[name="sex"][value="${sex}"]`).checked = true;
    if (t === "Master" && +form.elements.age.value > 14) setAge(8);
  });
  const setAge = (v) => { form.elements.age.value = v; ageOut.value = v; };
  form.elements.age.addEventListener("input", (e) => (ageOut.value = e.target.value));
  fare.addEventListener("input", () => { fareEdited = true; $(".auto-tag").textContent = "your fare"; });
  $$('input[name="pclass"]').forEach((r) => r.addEventListener("change", () => {
    $(".stub-class").innerHTML = `${r.value}<sup>${["st", "nd", "rd"][r.value - 1]}</sup>`;
    if (!fareEdited) fare.value = r.dataset.median;
    T.sound.beep(25, 0, 300);
  }));

  function readTicket() {
    const f = form.elements;
    const age = Number(f.age.value), fareV = Number(f.fare.value), family = Number(f.family.value);
    if (!Number.isFinite(fareV) || fareV < 0 || fareV > 600) return { error: "Fare must be between £0 and £600." };
    if (!Number.isInteger(family) || family < 0 || family > 10) return { error: "Family aboard must be a whole number from 0 to 10." };
    return {
      name: f.name.value.trim().slice(0, 80),
      title: f.title.value,
      sex: form.querySelector('input[name="sex"]:checked').value,
      age,
      pclass: Number(form.querySelector('input[name="pclass"]:checked').value),
      fare: fareV,
      family_size: family + 1,
      embarked: form.querySelector('input[name="embarked"]:checked').value,
    };
  }

  const errorEl = $(".form-error");
  const boardBtn = $(".board");
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const p = readTicket();
    errorEl.hidden = !p.error;
    if (p.error) { errorEl.textContent = p.error; return; }
    boardBtn.disabled = true; boardBtn.textContent = "Boarding…";
    try {
      const r = await fetch("/predict", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(p) });
      if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || `HTTP ${r.status}`);
      const data = await r.json();
      showResult(p, data);
    } catch (err) {
      errorEl.hidden = false;
      errorEl.textContent = `The purser could not stamp your ticket: ${err.message}`;
    } finally {
      boardBtn.disabled = false; boardBtn.textContent = "Board";
    }
  });

  /* ================================================================ the brass gauge */
  const gauge = $(".gauge");
  const arm = $(".needle-arm", gauge);
  const needle = $(".needle", gauge);
  const R = 128;
  const pt = (p, r = R) => [-r * Math.cos(p * Math.PI), -r * Math.sin(p * Math.PI)];
  const svgNS = "http://www.w3.org/2000/svg";
  [[0, 0.3, "#b0201a"], [0.3, 0.7, "#d99a1e"], [0.7, 1, "#2f8f5b"]].forEach(([a, b, c]) => {
    const [x1, y1] = pt(a), [x2, y2] = pt(b);
    const path = document.createElementNS(svgNS, "path");
    path.setAttribute("d", `M${x1} ${y1} A${R} ${R} 0 0 1 ${x2} ${y2}`);
    path.setAttribute("stroke", c);
    $(".zones", gauge).appendChild(path);
  });
  for (let k = 0; k <= 20; k++) {
    const p = k / 20, major = k % 2 === 0;
    const [x1, y1] = pt(p, 138), [x2, y2] = pt(p, major ? 116 : 124);
    const line = document.createElementNS(svgNS, "line");
    Object.entries({ x1, y1, x2, y2, stroke: "#2a2118", "stroke-width": major ? 2.4 : 1.2 }).forEach(([k2, v]) => line.setAttribute(k2, v));
    $(".ticks", gauge).appendChild(line);
    if (major) {
      const [tx, ty] = pt(p, 101);
      const text = document.createElementNS(svgNS, "text");
      text.setAttribute("x", tx); text.setAttribute("y", ty + 4);
      text.setAttribute("text-anchor", "middle");
      text.setAttribute("class", "tick-label");
      text.textContent = k * 5;
      $(".ticks", gauge).appendChild(text);
    }
  }
  arm.style.transform = "rotate(-90deg)";

  const pctEl = $(".readout .pct");
  function countUp(target) {
    if (T.reduced) { pctEl.textContent = target.toFixed(0); return; }
    const from = parseFloat(pctEl.textContent) || 0, t0 = performance.now(), dur = 1800;
    const step = (now) => {
      const k = Math.min(1, (now - t0) / dur), e = 1 - Math.pow(1 - k, 3);
      pctEl.textContent = (from + (target - from) * e).toFixed(0);
      if (k < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }

  const VERDICTS = {
    sinking: ["Abandon ship!", "The bulkheads won't hold. Women and children first, and you're neither lucky nor early."],
    uncertain: ["Hold fast", "The needle can't decide. Nor can the North Atlantic."],
    saved: ["Lifeboat secured", "A seat in boat No. 7, a blanket, and the Carpathia by dawn."],
  };

  function showResult(passenger, data) {
    const p = data.probability;
    // the needle: settle with a spring, tremble in the uncertain zone
    needle.classList.remove("tremble");
    arm.style.transform = `rotate(${-90 + p * 180}deg)`;
    countUp(p * 100);
    const [title, line] = VERDICTS[data.verdict];
    const v = $(".verdict");
    v.dataset.v = data.verdict;
    v.innerHTML = `<b>${title}</b><br><span style="text-transform:none;letter-spacing:0;font-family:var(--font-serif)">${line}</span>`;
    $(".model-used").textContent = `Oracle: ${data.model} · cross-validated accuracy ${(data.model_accuracy * 100).toFixed(1)}%`;
    setTimeout(() => effects(data.verdict), T.reduced ? 0 : 1500);
    drawChart(passenger, data.chart);
    listNeighbors(data.chart.neighbors);
    tellTheTelegraphist(passenger, data);
  }

  /* ================================================================ effects */
  let effectTimer;
  function effects(verdict) {
    clearTimeout(effectTimer);
    root.classList.remove("listing", "flooding");
    if (verdict === "sinking") {
      root.classList.add("listing", "flooding");
      T.sound.horn(2.4);
      navigator.vibrate?.([300, 100, 300]);
      effectTimer = setTimeout(() => root.classList.remove("listing", "flooding"), 7000);
    } else if (verdict === "uncertain") {
      needle.classList.add("tremble");
      T.sound.morse("..--..");
    } else {
      confetti();
      seagulls();
      T.sound.morse(".-. . ... -.-. ..- .");
    }
  }

  function confetti() {
    if (T.reduced) return;
    const cvs = $(".confetti");
    const dpr = Math.min(window.devicePixelRatio || 1, 1.6);
    const W = window.innerWidth, H = window.innerHeight;
    cvs.width = W * dpr; cvs.height = H * dpr;
    const g = cvs.getContext("2d");
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    const colors = ["#f5c542", "#a3262a", "#f4efe6", "#5ab4e6", "#d8a23a", "#1d7a5a"];
    const bits = Array.from({ length: 220 }, () => ({
      x: W / 2 + (Math.random() - 0.5) * 200, y: H * 0.45,
      vx: (Math.random() - 0.5) * 16, vy: -6 - Math.random() * 12,
      w: 6 + Math.random() * 8, h: 4 + Math.random() * 6, r: Math.random() * 6, vr: (Math.random() - 0.5) * 0.4,
      c: colors[(Math.random() * colors.length) | 0],
    }));
    const t0 = performance.now();
    const tick = (now) => {
      g.clearRect(0, 0, W, H);
      for (const b of bits) {
        b.x += b.vx; b.y += b.vy; b.vy += 0.32; b.vx *= 0.99; b.r += b.vr;
        g.save(); g.translate(b.x, b.y); g.rotate(b.r);
        g.fillStyle = b.c; g.fillRect(-b.w / 2, -b.h / 2, b.w, b.h * Math.abs(Math.cos(b.r * 2)));
        g.restore();
      }
      if (now - t0 < 4200) requestAnimationFrame(tick); else g.clearRect(0, 0, W, H);
    };
    requestAnimationFrame(tick);
  }

  function seagulls() {
    if (T.reduced) return;
    const sky = $(".gulls");
    for (let i = 0; i < 7; i++) {
      const gull = document.createElement("div");
      gull.className = "gull";
      gull.style.top = `${8 + Math.random() * 40}vh`;
      gull.style.setProperty("--dur", `${4.5 + Math.random() * 3}s`);
      gull.style.setProperty("--dy", `${(Math.random() - 0.7) * 20}vh`);
      gull.style.animationDelay = `${i * 0.35}s`;
      gull.style.width = `${38 + Math.random() * 30}px`;
      gull.innerHTML = '<svg viewBox="0 0 60 24"><path d="M2 14 Q16 0 30 14 Q44 0 58 14" fill="none" stroke="#f4efe6" stroke-width="3.5" stroke-linecap="round"/><circle cx="30" cy="15" r="2.5" fill="#f5c542"/></svg>';
      sky.appendChild(gull);
      setTimeout(() => gull.remove(), 11000);
    }
    setTimeout(() => T.toast("SQUAWK STOP SQUAWK STOP LAND IS NEAR STOP"), 900);
  }

  /* ================================================================ the passenger chart */
  function drawChart(you, chart) {
    const el = $("#scatter");
    if (!window.Plotly) {
      el.querySelector(".placeholder").textContent = "The chart room needs Plotly from the CDN. Check your connection.";
      return;
    }
    el.querySelector(".placeholder")?.remove();
    const byId = new Map(chart.passengers.map((p) => [p.id, p]));
    const fareY = (f) => Math.max(f, 1);
    const group = (s) => chart.passengers.filter((p) => p.survived === s);
    const trace = (rows, name, colorVar, symbol) => ({
      type: "scatter",
      mode: "markers",
      name,
      x: rows.map((p) => p.age),
      y: rows.map((p) => fareY(p.fare)),
      customdata: rows.map((p) => [p.name, p.pclass, p.age_estimated ? " (est.)" : "", p.fare]),
      hovertemplate: "<b>%{customdata[0]}</b><br>Age %{x}%{customdata[2]} · Class %{customdata[1]}<br>Fare £%{customdata[3]:.2f}<extra>" + name + "</extra>",
      marker: symbol === "x"
        ? { symbol: "x-thin-open", size: 8, color: color(colorVar), line: { width: 1.6, color: color(colorVar) }, opacity: 0.8 }
        : { symbol: "circle", size: 8, color: color(colorVar), line: { width: 1, color: "#0b1a2e" }, opacity: 0.85 },
    });
    const ny = chart.neighbors.map((n) => byId.get(n.id));
    const youX = you.age, youY = fareY(you.fare);
    const links = { x: [], y: [] };
    ny.forEach((n) => { links.x.push(youX, n.age, null); links.y.push(youY, fareY(n.fare), null); });
    const star = color("--star");
    const traces = [
      trace(group(0), "Perished", "--perished", "x"),
      trace(group(1), "Survived", "--survived", "o"),
      { type: "scatter", mode: "lines", name: "Your 5 nearest", x: links.x, y: links.y, hoverinfo: "skip",
        line: { color: star, width: 2, dash: "dot" }, showlegend: false },
      { type: "scatter", mode: "markers", name: "Nearest", x: ny.map((n) => n.age), y: ny.map((n) => fareY(n.fare)),
        customdata: ny.map((n) => [n.name, n.survived ? "survived" : "perished"]),
        hovertemplate: "<b>%{customdata[0]}</b><br>one of your 5 nearest · %{customdata[1]}<extra></extra>",
        marker: { symbol: "circle-open", size: 20, color: star, line: { width: 2.5, color: star } }, showlegend: false },
      { type: "scatter", mode: "markers+text", name: "You", x: [youX], y: [youY],
        text: [you.name || "You"], textposition: "top center", textfont: { color: star, family: "Federo", size: 14 },
        hovertemplate: `<b>${(you.name || "You").replace(/[<>&]/g, "")}</b><br>Age %{x} · Fare £${you.fare.toFixed(2)}<extra>You</extra>`,
        marker: { symbol: "star", size: 30, color: star, line: { width: 1.5, color: "#3a230b" } } },
    ];
    const titleFont = { color: "#efe6d2", family: "Federo", size: 14 };
    const axisStyle = { gridcolor: "rgba(243,217,142,.08)", zerolinecolor: "rgba(243,217,142,.12)", linecolor: "rgba(243,217,142,.25)",
      tickfont: { color: "#b9ae95", family: "Cormorant Garamond", size: 13 } };
    const layout = {
      paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)",
      margin: { l: 64, r: 16, t: 36, b: 52 },
      font: { family: "Cormorant Garamond", color: "#efe6d2" },
      xaxis: { ...axisStyle, title: { text: "Age (years)", font: titleFont }, range: [-2, 82] },
      yaxis: { ...axisStyle, title: { text: "Fare (£, log scale)", font: titleFont }, type: "log",
        tickvals: [1, 2, 5, 10, 20, 50, 100, 200, 500], ticktext: ["£1", "£2", "£5", "£10", "£20", "£50", "£100", "£200", "£500"] },
      legend: { orientation: "h", x: 0, y: 1.08, font: { family: "Federo", size: 13 } },
      hoverlabel: { bgcolor: "#0b1a2e", bordercolor: "#c9a227", font: { family: "Cormorant Garamond", size: 15, color: "#efe6d2" } },
      transition: T.reduced ? undefined : { duration: 600, easing: "cubic-in-out" },
    };
    window.Plotly.react(el, traces, layout, { responsive: true, displayModeBar: false });
  }

  function listNeighbors(neighbors) {
    const ol = $(".neighbors");
    ol.innerHTML = "";
    neighbors.forEach((n, i) => {
      const li = document.createElement("li");
      li.style.setProperty("--i", i);
      const name = document.createElement("span");
      name.className = "n-name"; name.textContent = n.name;
      const meta = document.createElement("span");
      meta.className = "n-meta";
      meta.textContent = `Class ${n.pclass} · ${n.age == null ? "age unknown" : `age ${n.age}`} · £${n.fare.toFixed(2)}`;
      const fate = document.createElement("span");
      fate.className = `fate ${n.survived ? "s" : "p"}`;
      fate.textContent = n.survived ? "● Survived" : "✕ Perished";
      li.append(name, meta, document.createElement("br"), fate);
      ol.appendChild(li);
    });
  }

  /* ================================================================ Harold's joke */
  const pop = $(".telegram-pop");
  $(".close", pop).addEventListener("click", () => (pop.hidden = true));
  const escapeHtml = (s) => s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

  async function tellTheTelegraphist(passenger, data) {
    const body = $(".pop-body", pop);
    pop.hidden = false;
    pop.style.animation = "none"; void pop.offsetWidth; pop.style.animation = "";
    body.textContent = "RECEIVING ···";
    let reply;
    try {
      const r = await fetch("/chat", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prediction: { probability: data.probability, verdict: data.verdict, model: data.model, passenger } }),
      });
      reply = (await r.json()).reply;
    } catch {
      reply = "LINE CUT STOP THE BRIDGE CANNOT REACH THE WIRELESS ROOM STOP";
    }
    const pct = `${(data.probability * 100).toFixed(0)}%`;
    const d = new Date();
    const chat = T.store.get("titanic.chat", []);
    chat.push({
      role: "assistant", kind: "bridge", content: reply, seen: false,
      note: `Re: ${passenger.name || "a passenger"} · ${pct} survival · ${data.model}`,
      at: `MGY · 14 APR 1912 · ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`,
    });
    T.store.set("titanic.chat", chat.slice(-40));
    // type it out
    if (T.reduced) { body.innerHTML = escapeHtml(reply).replace(/\bSTOP\b/g, '<span class="stop">STOP</span>'); return; }
    body.textContent = "";
    for (let i = 0; i < reply.length; i++) {
      body.textContent += reply[i];
      if (i % 3 === 0) T.sound.beep(Math.random() < 0.6 ? 40 : 100);
      await new Promise((r) => setTimeout(r, 18));
    }
    body.innerHTML = escapeHtml(reply).replace(/\bSTOP\b/g, '<span class="stop">STOP</span>');
  }
})();
