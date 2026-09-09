(function () {
  const launcher = document.getElementById("cq-launcher");
  const panel = document.getElementById("cq-panel");
  const body = document.getElementById("cq-body");
  const intro = document.getElementById("cq-intro");
  const form = document.getElementById("cq-form");
  const input = document.getElementById("cq-input");
  const send = form.querySelector("button");
  const meta = document.getElementById("cq-meta");

  const history = [];
  const { shortDate, longDate } = window.CQDates;

  let citationSeq = 0;
  let inFlight = null;

  const el = (tag, cls, text) => {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  };

  function sourceHref(cite) {
    if (cite.doc_id) return `/source/${encodeURIComponent(cite.doc_id)}`;
    return /^https?:\/\//i.test(cite.url || "") ? cite.url : "";
  }

  // ---------------------------------------------------------------- notices
  const notices = document.getElementById("notices");
  const noticeCount = document.getElementById("notice-count");

  function noticesFailed(reason) {
    notices.replaceChildren();
    const item = el("li", "notices-error");
    item.append(el("span", null, `Notices could not be loaded. ${reason}`));
    const retry = el("button", "retry", "Try again");
    retry.type = "button";
    retry.addEventListener("click", loadNotices);
    item.append(retry);
    notices.append(item);
    noticeCount.textContent = "–";
    meta.textContent = "index unavailable";
  }

  function loadNotices() {
    notices.replaceChildren(el("li", "loading", "Loading notices…"));
    fetch("/api/site/notices")
      .then(response => {
        if (!response.ok) throw new Error(`The server answered ${response.status}.`);
        return response.json();
      })
      .then(data => {
        if (!data || !Array.isArray(data.items)) throw new Error("The response was not in the expected form.");
        notices.replaceChildren();
        data.items.forEach(item => {
          const li = el("li");
          li.append(el("span", "date", shortDate(item.date)));
          li.append(el("span", "title", item.title || ""));
          const scan = /scan/i.test(item.source || "");
          li.append(el("span", "kind" + (scan ? " scan" : ""), scan ? "SCAN" : "PDF"));
          notices.append(li);
        });
        noticeCount.textContent = data.total;
        const s = data.stats || {};
        const updated = longDate((s.last_indexed || "").slice(0, 10));
        meta.textContent = `${s.documents} documents indexed · ${s.chunks} chunks`
          + (updated ? ` · updated ${updated}` : "");
      })
      .catch(err => noticesFailed(err.message));
  }
  loadNotices();

  // ---------------------------------------------------------------- panel
  function open() {
    panel.hidden = false;
    launcher.style.display = "none";
    launcher.setAttribute("aria-expanded", "true");
    input.focus();
  }
  function close() {
    panel.hidden = true;
    launcher.style.display = "flex";
    launcher.setAttribute("aria-expanded", "false");
    // Hiding the panel would otherwise drop focus onto the body, losing the keyboard
    // user's place in the page.
    launcher.focus();
  }
  launcher.addEventListener("click", open);
  document.getElementById("cq-close").addEventListener("click", close);
  document.addEventListener("keydown", e => { if (e.key === "Escape" && !panel.hidden) close(); });

  document.querySelectorAll(".cq-chips button").forEach(chip => {
    chip.addEventListener("click", () => ask(chip.textContent));
  });

  // ---------------------------------------------------------------- render
  function renderAnswer(text) {
    // [1] -> superscript marker, **bold** -> bold
    const node = el("div", "cq-answer");
    const html = String(text)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/\[([\d\s,]+)\]/g, "<sup>[$1]</sup>");
    node.innerHTML = html;
    return node;
  }

  function renderCitation(cite) {
    const card = el("div", "cq-cite");
    const bodyId = `cq-cite-body-${++citationSeq}`;

    const toggle = el("button", "cq-cite-toggle");
    toggle.type = "button";
    toggle.setAttribute("aria-expanded", "false");
    toggle.setAttribute("aria-controls", bodyId);

    const top = el("div", "cq-cite-top");
    if (cite.n) top.append(el("span", "cq-cite-n", `[${cite.n}]`));
    top.append(el("span", "cq-kind " + (cite.kind || "page"),
      cite.kind === "circular" ? "PDF" : (cite.kind || "page").toUpperCase()));
    top.append(el("b", null, cite.title || "Untitled document"));
    toggle.append(top);
    const line = [cite.source, cite.section, longDate(cite.date)].filter(Boolean).join(" · ");
    toggle.append(el("small", null, line));
    card.append(toggle);

    const excerpt = el("div", "cq-cite-body", cite.preview || "");
    excerpt.id = bodyId;
    excerpt.hidden = true;
    card.append(excerpt);

    toggle.addEventListener("click", () => {
      const nowOpen = excerpt.hidden;
      excerpt.hidden = !nowOpen;
      toggle.setAttribute("aria-expanded", String(nowOpen));
      card.classList.toggle("open", nowOpen);
    });

    const href = sourceHref(cite);
    if (href) {
      const link = el("a", "cq-cite-open", "Read the full document");
      link.href = href;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      card.append(link);
    } else {
      card.append(el("p", "cq-cite-missing", "The full document is not available to open."));
    }
    return card;
  }

  function renderDegraded(degraded, mode) {
    const note = el("div", "cq-degraded");
    note.append(el("strong", null, degraded.reason === "timeout"
      ? "Answered from the source text"
      : "Working without the writing model"));
    note.append(el("span", null, degraded.detail || ""));
    if (mode) note.append(el("small", null, mode));
    return note;
  }

  // "searching circulars..." for two minutes tells the student nothing. The label moves
  // on with the request, and the request can be stopped.
  const STAGES = [
    [0, "searching circulars..."],
    [2500, "reading the matching sections..."],
    [7000, "writing the answer..."],
    [20000, "the model is slower than usual, still working..."],
  ];

  function typing(onCancel) {
    const node = el("div", "cq-typing");
    const label = el("span", null, STAGES[0][1]);
    node.append(el("i"), el("i"), el("i"), label);

    const cancel = el("button", "cq-cancel", "Stop");
    cancel.type = "button";
    cancel.addEventListener("click", onCancel);
    node.append(cancel);

    const timers = STAGES.slice(1).map(([after, text]) =>
      setTimeout(() => { label.textContent = text; }, after));
    node.stop = () => timers.forEach(clearTimeout);
    return node;
  }

  function scroll() { body.scrollTop = body.scrollHeight; }

  function problem(title, detail, retry) {
    const box = el("div", "cq-refusal", title);
    if (detail) box.append(el("span", null, detail));
    if (retry) {
      const again = el("button", "retry", "Try again");
      again.type = "button";
      again.addEventListener("click", () => ask(retry));
      box.append(again);
    }
    body.append(box);
  }

  // ---------------------------------------------------------------- ask
  async function ask(question) {
    question = (question || "").trim();
    if (!question || inFlight) return;
    if (intro.parentNode) intro.remove();

    body.append(el("div", "cq-user", question));
    const controller = new AbortController();
    inFlight = controller;
    const wait = typing(() => controller.abort());
    body.append(wait);
    scroll();
    input.value = "";
    send.disabled = true;

    let data;
    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, history: history.slice(-6) }),
        signal: controller.signal,
      });
      if (!response.ok) throw new Error("HTTP " + response.status);
      data = await response.json();
    } catch (err) {
      wait.stop();
      wait.remove();
      if (err.name === "AbortError") {
        problem("Stopped before an answer came back.", null, question);
      } else {
        problem("The assistant is not reachable right now.", String(err), question);
      }
      return;
    } finally {
      inFlight = null;
      send.disabled = false;
      input.focus();
      scroll();
    }

    wait.stop();
    wait.remove();
    // A failure to display a delivered answer is not a failure to reach the assistant,
    // and must not be reported as one.
    try {
      if (data.refused) {
        const box = el("div", "cq-refusal", data.answer);
        box.append(el("span", null, "Nothing in the indexed college content covers this question."));
        body.append(box);
      } else {
        body.append(renderAnswer(data.answer));
        if (data.degraded) body.append(renderDegraded(data.degraded, data.mode));
        (data.citations || []).forEach(c => body.append(renderCitation(c)));
      }
      history.push({ role: "user", content: question });
      history.push({ role: "assistant", content: data.answer });
    } catch (err) {
      problem("The answer came back but could not be displayed.", String(err), null);
    }
    scroll();
  }

  form.addEventListener("submit", e => { e.preventDefault(); ask(input.value); });
})();
