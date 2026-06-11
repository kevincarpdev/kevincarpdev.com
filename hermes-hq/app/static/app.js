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
  const addMsg = (role, who, text) => {
    const d = document.createElement("div");
    d.className = "msg " + role;
    const w = document.createElement("div"); w.className = "who"; w.textContent = who;
    const b = document.createElement("div"); b.className = "body"; b.textContent = text;
    d.append(w, b); log.appendChild(d); log.scrollTop = log.scrollHeight;
    return d;
  };
  if (log) log.scrollTop = log.scrollHeight;
  async function sendChat() {
    const text = input.value.trim();
    if (!text) return;
    input.value = ""; send.disabled = true;
    addMsg("user", "you", text);
    const spin = addMsg("assistant", "HQ", "");
    spin.querySelector(".body").innerHTML = '<span class="thinking">thinking…</span>';
    try {
      const out = await api(`/api/project/${slug}/chat`, { message: text });
      spin.querySelector(".body").textContent = out.reply;
    } catch (e) {
      spin.querySelector(".body").textContent = "Error: " + e.message;
    }
    send.disabled = false; log.scrollTop = log.scrollHeight; input.focus();
  }
  send?.addEventListener("click", sendChat);
  input?.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendChat(); }
  });

  // ---- drafting ----
  $("#draftGo")?.addEventListener("click", async () => {
    const btn = $("#draftGo"), spin = $("#draftSpin"), out = $("#draftOut"), ins = $("#draftInsight");
    btn.disabled = true; spin.style.display = "inline";
    try {
      const o = await api(`/api/project/${slug}/draft`, {
        contact_id: $("#draftContact").value,
        channel: $("#draftChannel").value,
        intent: $("#draftIntent").value,
      });
      out.textContent = o.draft;
      if (o.insight) { ins.style.display = "block"; ins.textContent = "memory says: " + o.insight; }
    } catch (e) { out.textContent = "Error: " + e.message; }
    btn.disabled = false; spin.style.display = "none";
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
    } catch (e) { alert(e.message); }
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

  // ---- notes ----
  $("#notesSave")?.addEventListener("click", async () => {
    await api(`/api/project/${slug}/notes`, { notes: $("#projNotes").value });
    flash($("#notesFlash"), "saved ✓");
  });
}

// ---- jobs ----
$("#jAdd")?.addEventListener("click", async () => {
  await api("/api/jobs", {
    title: $("#jTitle").value, platform: $("#jPlatform").value, url: $("#jUrl").value,
    client: $("#jClient").value, budget: $("#jBudget").value, description: $("#jDesc").value,
  });
  location.reload();
});
$$("tr[data-jid]").forEach((row) => {
  const jid = row.dataset.jid;
  const detail = $(`tr[data-jdetail="${jid}"]`);
  $(".j-status", row)?.addEventListener("change", (e) =>
    api(`/api/jobs/${jid}/status`, { status: e.target.value }));
  $(".j-score", row)?.addEventListener("click", async (e) => {
    e.target.disabled = true; e.target.textContent = "…";
    try {
      const o = await api(`/api/jobs/${jid}/score`);
      detail.style.display = ""; $(".j-notes", detail).textContent = o.notes;
      location.reload();
    } catch (err) { alert(err.message); e.target.disabled = false; e.target.textContent = "SCORE"; }
  });
  $(".j-proposal", row)?.addEventListener("click", async (e) => {
    e.target.disabled = true; e.target.textContent = "…";
    try {
      const o = await api(`/api/jobs/${jid}/proposal`);
      detail.style.display = ""; const p = $(".j-prop", detail);
      p.style.display = ""; p.textContent = o.proposal;
    } catch (err) { alert(err.message); }
    e.target.disabled = false; e.target.textContent = "PROPOSAL";
  });
});
