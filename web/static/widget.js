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
  const MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"];

  const el = (tag, cls, text) => {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  };

  function shortDate(iso) {
    if (!iso) return "";
    const [y, m, d] = iso.split("-");
    return `${d} ${MONTHS[Number(m) - 1]} ${y.slice(2)}`;
  }

  function longDate(iso) {
    if (!iso) return "";
    const [y, m, d] = iso.split("-");
    return `${Number(d)} ${MONTHS[Number(m) - 1][0]}${MONTHS[Number(m) - 1].slice(1).toLowerCase()} ${y}`;
  }

  // ---------------------------------------------------------------- notices
  fetch("/api/site/notices").then(r => r.json()).then(data => {
    const list = document.getElementById("notices");
    list.innerHTML = "";
    data.items.forEach(item => {
      const li = el("li");
      li.append(el("span", "date", shortDate(item.date)));
      li.append(el("span", "title", item.title));
      const scan = /scan/i.test(item.source);
      li.append(el("span", "kind" + (scan ? " scan" : ""), scan ? "SCAN" : "PDF"));
      list.append(li);
    });
    document.getElementById("notice-count").textContent = data.total;
    const s = data.stats;
    meta.textContent = `${s.documents} documents indexed · ${s.chunks} chunks · updated ${longDate((s.last_indexed || "").slice(0, 10))}`;
  }).catch(() => { meta.textContent = "index unavailable"; });

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
    const html = text
      .replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/\[([\d\s,]+)\]/g, "<sup>[$1]</sup>");
    node.innerHTML = html;
    return node;
  }

  function renderCitation(cite) {
    const card = el("div", "cq-cite");
    const top = el("div", "cq-cite-top");
    top.append(el("span", "cq-kind " + (cite.kind || "page"),
      cite.kind === "circular" ? "PDF" : (cite.kind || "page").toUpperCase()));
    top.append(el("b", null, cite.title));
    card.append(top);
    const line = [cite.source, cite.section, longDate(cite.date)].filter(Boolean).join(" · ");
    card.append(el("small", null, line));
    card.append(el("div", "cq-cite-body", cite.preview || ""));
    card.addEventListener("click", () => card.classList.toggle("open"));
    return card;
  }

  function typing() {
    const node = el("div", "cq-typing");
    node.append(el("i"), el("i"), el("i"),
      el("span", null, "searching circulars..."));
    return node;
  }

  function scroll() { body.scrollTop = body.scrollHeight; }

  // ---------------------------------------------------------------- ask
  async function ask(question) {
    question = (question || "").trim();
    if (!question) return;
    if (intro.parentNode) intro.remove();

    body.append(el("div", "cq-user", question));
    const wait = typing();
    body.append(wait);
    scroll();
    input.value = "";
    send.disabled = true;

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, history: history.slice(-6) }),
      });
      if (!response.ok) throw new Error("HTTP " + response.status);
      const data = await response.json();
      wait.remove();

      if (data.refused) {
        const box = el("div", "cq-refusal", data.answer);
        box.append(el("span", null, "Nothing in the indexed college content covers this question."));
        body.append(box);
      } else {
        body.append(renderAnswer(data.answer));
        data.citations.forEach(c => body.append(renderCitation(c)));
      }

      history.push({ role: "user", content: question });
      history.push({ role: "assistant", content: data.answer });
    } catch (err) {
      wait.remove();
      const box = el("div", "cq-refusal", "The assistant is not reachable right now.");
      box.append(el("span", null, String(err)));
      body.append(box);
    } finally {
      send.disabled = false;
      scroll();
      input.focus();
    }
  }

  form.addEventListener("submit", e => { e.preventDefault(); ask(input.value); });
})();
