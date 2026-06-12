// Hermes HQ — vanilla client logic
async function api(url, body) {
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  return r.json();
}
const $ = (s, el) => (el || document).querySelector(s);
const $$ = (s, el) => [...(el || document).querySelectorAll(s)];
const flash = (el, msg) => { if (el) { el.textContent = msg; setTimeout(() => (el.textContent = ""), 2500); } };

// ---- app chrome: generation modal + toasts ----
document.body.insertAdjacentHTML("beforeend", `
<div class="busy-overlay" id="busyOverlay"><div class="busy-box">
  <div class="busy-title"><span id="busyTitle">WORKING</span><span class="busy-cursor"></span></div>
  <div class="busy-sub" id="busySub"></div>
  <div class="busy-note">ONE GENERATION AT A TIME — CONTROLS LOCKED SO TOKENS AREN'T WASTED</div>
</div></div>
<div class="toasts" id="toasts"></div>`);
let BUSY = false;
function toast(msg, err) {
  const t = document.createElement("div");
  t.className = "toast" + (err ? " err" : "");
  t.textContent = msg;
  $("#toasts").append(t);
  setTimeout(() => t.remove(), 4200);
}
async function generate(title, sub, fn) {
  if (BUSY) { toast("Already generating — hang on.", true); return null; }
  BUSY = true;
  $("#busyTitle").textContent = title;
  $("#busySub").textContent = sub || "";
  $("#busyOverlay").classList.add("on");
  try {
    return await fn();
  } catch (e) {
    toast("Error: " + e.message, true);
    return null;
  } finally {
    BUSY = false;
    $("#busyOverlay").classList.remove("on");
  }
}

// Minimal, safe markdown → HTML (escape first, protect code spans)
function mdToHtml(raw) {
  const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  let t = esc(raw);
  const slots = [];
  t = t.replace(/```\w*\n?([\s\S]*?)```/g, (m, c) => {
    slots.push(`<pre><code>${c.replace(/\n$/, "")}</code></pre>`);
    return `\u0000${slots.length - 1}\u0000`;
  });
  t = t.replace(/`([^`\n]+)`/g, (m, c) => {
    slots.push(`<code>${c}</code>`);
    return `\u0000${slots.length - 1}\u0000`;
  });
  t = t.replace(/^#{1,4} +(.+)$/gm, "<h5>$1</h5>");
  t = t.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  t = t.replace(/\[([^\]]+)\]\((https?:[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  t = t.replace(/^(?:[-*•]|\d+\.) +(.+)$/gm, "<li>$1</li>");
  t = t.replace(/(?:<li>.*<\/li>\n?)+/g, (m) => `<ul>${m.replace(/\n/g, "")}</ul>`);
  t = t.replace(/\n?(<(?:ul|h5|pre)\b)/g, "$1").replace(/(<\/(?:ul|h5|pre)>)\n?/g, "$1");
  t = t.replace(/\u0000(\d+)\u0000/g, (m, i) => slots[+i]);
  return t;
}
function setBody(msgEl, text) {
  const b = msgEl.querySelector(".body");
  b.dataset.raw = text;
  if (msgEl.classList.contains("assistant")) b.innerHTML = mdToHtml(text);
  else b.textContent = text;
}

// ---- tabs ----
const tabs = $(".tabs");
if (tabs) {
  const slug = tabs.dataset.proj;
  $$(".tabs button").forEach((b) =>
    b.addEventListener("click", () => {
      $$(".tabs button").forEach((x) => x.classList.remove("on"));
      $$(".tab-pane").forEach((x) => x.classList.remove("on"));
      b.classList.add("on");
      $("#pane-" + b.dataset.tab).classList.add("on");
    })
  );

  // ---- workspace chat ----
  const log = $("#chatLog"), input = $("#chatInput"), send = $("#chatSend");
  const nearBottom = () => log.scrollHeight - log.scrollTop - log.clientHeight < 140;
  const scrollDown = () => (log.scrollTop = log.scrollHeight);
  const addMsg = (role, who, text) => {
    const d = document.createElement("div");
    d.className = "msg " + role;
    const w = document.createElement("div"); w.className = "who";
    w.innerHTML = `${who} <button class="copymsg" title="copy">copy</button>`;
    const b = document.createElement("div"); b.className = "body";
    d.append(w, b); setBody(d, text); log.appendChild(d); scrollDown();
    return d;
  };
  if (log) {
    // render markdown + add copy buttons on server-rendered history
    $$(".msg", log).forEach((m) => {
      const b = $(".body", m);
      const raw = b.textContent;
      setBody(m, raw);
      $(".who", m).insertAdjacentHTML("beforeend", ' <button class="copymsg" title="copy">copy</button>');
    });
    scrollDown();
    log.addEventListener("click", (e) => {
      if (!e.target.classList.contains("copymsg")) return;
      const body = $(".body", e.target.closest(".msg"));
      navigator.clipboard.writeText(body.dataset.raw || body.textContent);
      e.target.textContent = "copied"; setTimeout(() => (e.target.textContent = "copy"), 1200);
    });
  }
  async function sendChat() {
    const text = input.value.trim();
    if (!text) return;
    input.value = ""; send.disabled = true;
    addMsg("user", "you", text);
    const spin = addMsg("assistant", "HQ", "");
    spin.querySelector(".body").innerHTML = '<span class="thinking">thinking…</span>';
    try {
      const out = await api(`/api/project/${slug}/chat`, { message: text });
      const stay = nearBottom();
      setBody(spin, out.reply);
      if (stay) scrollDown();
    } catch (e) {
      spin.querySelector(".body").textContent = "Error: " + e.message;
    }
    send.disabled = false; input.focus();
  }
  send?.addEventListener("click", sendChat);
  input?.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendChat(); }
  });

  // ---- drafting ----
  $("#draftGo")?.addEventListener("click", async () => {
    const out = $("#draftOut"), ins = $("#draftInsight");
    const sel = $("#draftContact");
    const who = sel.options[sel.selectedIndex]?.text.split(" — ")[0] || "contact";
    const o = await generate(`DRAFTING ${$("#draftChannel").value.toUpperCase()}`,
      `To ${who} — pulling their style notes and what memory knows about them`,
      () => api(`/api/project/${slug}/draft`, {
        contact_id: sel.value,
        channel: $("#draftChannel").value,
        intent: $("#draftIntent").value,
      }));
    if (!o) return;
    out.textContent = o.draft;
    if (o.insight) { ins.style.display = "block"; ins.textContent = "memory says: " + o.insight; }
    toast("Draft ready — edit inline, copy, then mark as sent.");
  });
  $("#draftCopy")?.addEventListener("click", () => {
    navigator.clipboard.writeText($("#draftOut").textContent);
    $("#draftCopy").textContent = "copied"; setTimeout(() => ($("#draftCopy").textContent = "copy"), 1500);
  });
  $("#draftSent")?.addEventListener("click", async () => {
    try {
      await api(`/api/project/${slug}/sent`, {
        contact_id: $("#draftContact").value, content: $("#draftOut").textContent,
      });
      $("#draftSent").textContent = "logged ✓";
      setTimeout(() => ($("#draftSent").textContent = "mark as sent"), 2000);
      toast("Sent message logged → memory learns your voice.");
    } catch (e) { toast("Error: " + e.message, true); }
  });
  $("#inboundGo")?.addEventListener("click", async () => {
    try {
      const o = await api(`/api/project/${slug}/inbound`, {
        contact_id: $("#draftContact").value, content: $("#inboundText").value,
      });
      $("#inboundText").value = "";
      flash($("#inboundFlash"), o.honcho ? "logged → memory ✓" : "logged (honcho off)");
    } catch (e) { flash($("#inboundFlash"), "error: " + e.message); }
  });

  // ---- people ----
  $$(".contact-card[data-cid]").forEach((card) => {
    const cid = card.dataset.cid;
    $(".c-save", card)?.addEventListener("click", async () => {
      await api(`/api/contact/${cid}`, {
        role: $(".c-role", card).value, email: $(".c-email", card).value,
        slack: $(".c-slack", card).value, style_notes: $(".c-style", card).value,
      });
      flash($(".c-flash", card), "saved ✓");
    });
    $(".c-insight", card)?.addEventListener("click", async () => {
      const out = $(".c-insight-out", card);
      out.style.display = "block"; out.textContent = "asking memory…";
      const r = await fetch(`/api/contact/${cid}/insight`);
      out.textContent = (await r.json()).insight;
    });
  });
  $("#newContactGo")?.addEventListener("click", async () => {
    const name = $("#newName").value.trim();
    if (!name) return;
    await api(`/api/org/${$("#newContactGo").dataset.org}/contact`, {
      name, role: $("#newRole").value,
    });
    location.reload();
  });

  // ---- recent drafts: delete ----
  $$(".contact-card[data-did]").forEach((card) => {
    $(".d-del", card)?.addEventListener("click", async () => {
      if (!confirm("Delete this draft?")) return;
      await api(`/api/drafts/${card.dataset.did}/delete`);
      card.remove();
    });
  });

  // ---- notes ----
  $("#notesSave")?.addEventListener("click", async () => {
    await api(`/api/project/${slug}/notes`, { notes: $("#projNotes").value });
    flash($("#notesFlash"), "saved ✓");
  });
}

// ---- jobs (accordion cards) ----
$("#jAdd")?.addEventListener("click", async () => {
  try {
    await api("/api/jobs", {
      title: $("#jTitle").value, platform: $("#jPlatform").value, url: $("#jUrl").value,
      client: $("#jClient").value, budget: $("#jBudget").value, description: $("#jDesc").value,
      screener: $("#jScreener")?.value || "",
    });
    location.reload();
  } catch (e) { toast("Error: " + e.message, true); }
});
$$(".lead").forEach((card) => {
  const jid = card.dataset.jid, title = card.dataset.title || "lead";
  const open = () => card.classList.add("open");
  $(".lead-head", card).addEventListener("click", (e) => {
    if (e.target.closest("button, select, a, textarea")) return;
    card.classList.toggle("open");
  });
  $(".j-delete", card)?.addEventListener("click", async () => {
    if (!confirm(`Delete "${title}" and its proposal?`)) return;
    await api(`/api/jobs/${jid}/delete`);
    card.remove(); toast("Lead deleted.");
  });
  $(".j-screener-save", card)?.addEventListener("click", async () => {
    await api(`/api/jobs/${jid}/screener`, { screener: $(".j-screener", card).value });
    flash($(".j-flash", card), "saved ✓"); toast("Screener questions saved.");
  });
  $(".j-status", card)?.addEventListener("change", async (e) => {
    await api(`/api/jobs/${jid}/status`, { status: e.target.value });
    toast(`Status → ${e.target.value}`);
  });
  $(".j-copy", card)?.addEventListener("click", () => {
    navigator.clipboard.writeText($(".j-prop", card).textContent);
    toast("Proposal copied.");
  });
  $(".j-score", card)?.addEventListener("click", async () => {
    const badge = $(".fit-badge", card);
    if (!badge.classList.contains("none") &&
        !confirm("Already scored — regenerate and spend tokens?")) return;
    const o = await generate("SCORING FIT", `${title} — comparing against your resume and past-work library`,
      () => api(`/api/jobs/${jid}/score`));
    if (!o) return;
    open(); $(".j-notes", card).textContent = o.notes;
    const s = o.score;
    badge.textContent = s === null ? "—" : Math.round(s);
    badge.className = "fit-badge " + (s === null ? "none" : s >= 70 ? "hi" : s >= 45 ? "mid" : "lo");
    toast("Fit scored: " + badge.textContent);
  });
  $(".j-proposal", card)?.addEventListener("click", async () => {
    const p = $(".j-prop", card);
    if (p.dataset.has === "1" &&
        !confirm("A proposal already exists — regenerate and spend tokens?")) return;
    const screeners = ($(".j-screener", card)?.value || "").trim();
    const o = await generate("COMPOSING PROPOSAL",
      `${title}${screeners ? " — answering screener questions too" : ""}`,
      () => api(`/api/jobs/${jid}/proposal`));
    if (!o) return;
    open(); p.textContent = o.proposal; p.dataset.has = "1";
    toast("Proposal ready — review, then copy.");
  });
});
