/* telegraphist.js — the wireless room: send telegrams to /chat, type the pandas tape and the reply. */
(() => {
  "use strict";
  const T = window.Titanic;
  const $ = (s, el = document) => el.querySelector(s);
  const log = $(".log");
  const form = $(".compose");
  const input = $("#message");
  const sendBtn = $(".send");
  const key = $(".key");
  const lamp = $(".lamp");
  const STORE = "titanic.chat";

  let entries = T.store.get(STORE, []);
  const save = () => T.store.set(STORE, entries.slice(-40));

  /* ---------------------------------------------------------------- helpers */
  const shipTime = (d = new Date()) =>
    `MGY · 14 APR 1912 · ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;

  const escapeHtml = (s) => s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const highlightStops = (s) => escapeHtml(s).replace(/\bSTOP\b/gi, '<span class="stop">STOP</span>');

  let skipTyping = false;
  log.addEventListener("click", () => { skipTyping = true; });

  /** Type text into el one character at a time, tapping the key and (optionally) beeping. */
  function typeInto(el, text, speed = 16, beep = false) {
    if (T.reduced) { el.textContent = text; return Promise.resolve(); }
    el.classList.add("caret");
    el.textContent = "";
    return new Promise((resolve) => {
      let i = 0;
      const step = () => {
        if (skipTyping) { el.textContent = text; i = text.length; }
        else {
          const burst = text.length > 400 ? 3 : 1;
          el.textContent += text.slice(i, i + burst);
          i += burst;
          if (i % 2 === 0) tap();
          if (beep && i % 3 === 0 && /\w/.test(text[i] || "")) T.sound.beep(Math.random() < 0.6 ? 45 : 110);
          el.closest(".log") && (log.scrollTop = log.scrollHeight);
        }
        if (i < text.length) setTimeout(step, speed + (text[i - 1] === " " ? speed * 1.5 : 0));
        else { el.classList.remove("caret"); resolve(); }
      };
      step();
    });
  }

  let tapTimer;
  function tap() {
    if (!key) return;
    key.classList.add("down");
    clearTimeout(tapTimer);
    tapTimer = setTimeout(() => key.classList.remove("down"), 55);
  }
  let keying = 0;
  function startKeying() {
    stopKeying();
    if (T.reduced) return;
    const go = () => { tap(); keying = setTimeout(go, 90 + Math.random() * 260); };
    go();
  }
  function stopKeying() { clearTimeout(keying); keying = 0; }

  /* ---------------------------------------------------------------- rendering */
  function stampFor(entry) {
    if (entry.cut) return "Line cut";
    if (entry.kind === "bridge") return "Relayed from the Bridge";
    if (!entry.steps?.length) return "";
    if (entry.verified === false) return "Exact figures";
    return entry.corrected ? "Figures corrected" : "Figures verified";
  }

  function buildIncoming(entry) {
    const li = $("#tpl-incoming").content.firstElementChild.cloneNode(true);
    $(".stamp", li).textContent = entry.at || shipTime();
    if (entry.cut) li.classList.add("cut");
    if (entry.kind === "bridge") li.classList.add("bridge");
    if (entry.steps?.length && !entry.cut) li.classList.add(entry.corrected || entry.verified === false ? "corrected" : "verified");
    const stamp = stampFor(entry);
    if (stamp) {
      const r = document.createElement("span");
      r.className = "rubber"; r.textContent = stamp;
      li.appendChild(r);
    }
    if (entry.note) {
      const n = document.createElement("p");
      n.className = "slip-note";
      n.style.cssText = "margin:0 0 .5rem;font-style:italic;color:#5a4a36";
      n.textContent = entry.note;
      $(".tapes", li).before(n);
    }
    return li;
  }

  function buildTape(step) {
    const fig = $("#tpl-tape").content.firstElementChild.cloneNode(true);
    if (!step.ok) fig.classList.add("error");
    return fig;
  }

  async function playIncoming(li, entry, animate) {
    const tapes = $(".tapes", li);
    const body = $(".slip-body", li);
    for (const step of entry.steps || []) {
      const fig = buildTape(step);
      tapes.appendChild(fig);
      const code = $(".tape-code code", fig), result = $(".tape-result", fig);
      if (animate) {
        await typeInto(code, step.code, 22);
        await typeInto(result, step.result, 4);
      } else { code.textContent = step.code; result.textContent = step.result; }
    }
    if (animate) await typeInto(body, entry.content, 18, true);
    body.innerHTML = highlightStops(entry.content);
    log.scrollTop = log.scrollHeight;
  }

  function renderOutgoing(entry) {
    const li = $("#tpl-outgoing").content.firstElementChild.cloneNode(true);
    $(".stamp", li).textContent = entry.at || shipTime();
    $(".slip-body", li).textContent = entry.content;
    log.appendChild(li);
    log.scrollTop = log.scrollHeight;
  }

  async function renderAll() {
    log.innerHTML = "";
    for (const e of entries) {
      if (e.role === "user") renderOutgoing(e);
      else {
        const li = buildIncoming(e);
        log.appendChild(li);
        const fresh = e.seen === false;
        if (fresh) { e.seen = true; save(); }
        await playIncoming(li, e, fresh);
      }
    }
  }

  /* ---------------------------------------------------------------- sending */
  async function send(text) {
    text = text.trim();
    if (!text || sendBtn.disabled) return;
    const history = entries.filter((e) => e.kind !== "bridge").map(({ role, content }) => ({ role, content }));
    const out = { role: "user", content: text, at: shipTime() };
    entries.push(out); save();
    renderOutgoing(out);
    input.value = "";
    setBusy(true);

    const pending = document.createElement("li");
    pending.className = "telegram incoming";
    pending.innerHTML = '<p class="slip-body receiving" aria-label="Receiving">RECEIVING <span>·</span><span>·</span><span>·</span></p>';
    log.appendChild(pending);
    log.scrollTop = log.scrollHeight;
    startKeying();

    let data;
    try {
      const r = await fetch("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, history }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      data = await r.json();
    } catch (err) {
      data = { reply: "LINE CUT STOP THE SHIP'S OWN SERVER DID NOT ANSWER STOP IS uv run titanic-app STILL RUNNING STOP", steps: [], line_cut: true };
    }
    stopKeying();
    pending.remove();

    const entry = {
      role: "assistant", content: data.reply, steps: data.steps || [], cut: !!data.line_cut,
      verified: data.verified, corrected: data.corrected, at: shipTime(),
    };
    entries.push(entry); save();
    const li = buildIncoming(entry);
    log.appendChild(li);
    skipTyping = false;
    await playIncoming(li, entry, true);
    if (entry.cut) setLamp({ online: false });
    setBusy(false);
    input.focus({ preventScroll: true });
  }

  function setBusy(busy) {
    sendBtn.disabled = busy;
    document.querySelectorAll(".suggestion").forEach((b) => (b.disabled = busy));
    sendBtn.innerHTML = busy ? '<span aria-hidden="true">⌁</span> Keying…' : '<span aria-hidden="true">⚡</span> Send';
  }

  form.addEventListener("submit", (e) => { e.preventDefault(); send(input.value); });
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(input.value); }
  });
  document.querySelectorAll(".suggestion").forEach((b) => b.addEventListener("click", () => send(b.textContent)));
  $(".new-roll").addEventListener("click", () => {
    entries = []; save(); log.innerHTML = "";
    T.toast("FRESH ROLL OF PAPER LOADED STOP");
  });

  /* ---------------------------------------------------------------- is the line open? */
  function setLamp(s) {
    const text = $(".lamp-text", lamp);
    if (s.online && s.model_available) { lamp.dataset.state = "online"; text.textContent = `Line open · ${s.model}`; }
    else if (s.online) { lamp.dataset.state = "cut"; text.textContent = `Model missing · ollama pull ${s.model}`; }
    else { lamp.dataset.state = "cut"; text.textContent = "Line cut · start Ollama"; }
  }
  fetch("/api/telegraph").then((r) => r.json()).then(setLamp).catch(() => setLamp({ online: false }));

  renderAll();
})();
