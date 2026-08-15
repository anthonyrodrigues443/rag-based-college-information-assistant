(function () {
  const $ = id => document.getElementById(id);
  let token = sessionStorage.getItem("cq_token") || "";

  const api = async (path, options = {}) => {
    const response = await fetch(path, {
      ...options,
      headers: { "X-Admin-Token": token, ...(options.headers || {}) },
    });
    if (response.status === 401) throw new Error("Unauthorised. Check the admin token.");
    if (!response.ok) throw new Error(await response.text());
    return response.json();
  };

  const log = message => {
    const box = $("log");
    box.hidden = false;
    box.textContent = message + "\n" + box.textContent;
  };

  function renderStats(stats) {
    $("stats").innerHTML = [
      [stats.documents, "documents"],
      [stats.chunks, "chunks"],
      [stats.vectors, "vectors (384-d)"],
      [stats.seed_documents, "from seed corpus"],
      [stats.uploaded_documents, "uploaded"],
    ].map(([value, label]) => `<div class="stat"><b>${value}</b><span>${label}</span></div>`).join("");
  }

  function renderDocs(docs) {
    $("doc-count").textContent = `(${docs.length})`;
    $("docs").innerHTML = docs.map(doc => `
      <tr>
        <td>${escapeHtml(doc.title || "")}</td>
        <td><span class="tag">${doc.kind || "page"}</span></td>
        <td><span class="tag ${doc.origin === "upload" ? "upload" : ""}">${doc.origin || ""}</span></td>
        <td>${doc.n_chunks}</td>
        <td>${(doc.indexed_at || "").replace("T", " ").replace("+00:00", "")}</td>
        <td><button class="del" data-id="${doc.doc_id}">remove</button></td>
      </tr>`).join("");
    document.querySelectorAll(".del").forEach(button => {
      button.addEventListener("click", async () => {
        if (!confirm("Remove this document from the index?")) return;
        const data = await api("/api/admin/document/" + button.dataset.id, { method: "DELETE" });
        log(`removed ${data.removed_chunks} chunks`);
        refresh();
      });
    });
  }

  const escapeHtml = s => s.replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  async function refresh() {
    const data = await api("/api/admin/status");
    renderStats(data.stats);
    renderDocs(data.documents);
  }

  function report(payload) {
    payload.results.forEach(result => {
      log(result.skipped
        ? `SKIPPED  ${result.title} — ${result.skipped}`
        : `INDEXED  ${result.title} — ${result.chunks} chunks, ${result.words || "?"} words`);
    });
    if (payload.elapsed_ms) log(`done in ${payload.elapsed_ms} ms`);
    refresh();
  }

  // ---------------------------------------------------------------- auth
  async function connect() {
    token = $("token").value.trim();
    const msg = $("auth-msg");
    try {
      await api("/api/admin/status");
      sessionStorage.setItem("cq_token", token);
      msg.textContent = "connected";
      msg.className = "msg good";
      $("console").hidden = false;
      refresh();
    } catch (err) {
      msg.textContent = err.message;
      msg.className = "msg bad";
      $("console").hidden = true;
    }
  }
  $("connect").addEventListener("click", connect);
  $("token").addEventListener("keydown", e => { if (e.key === "Enter") connect(); });
  if (token) { $("token").value = token; connect(); }

  // ---------------------------------------------------------------- uploads
  const drop = $("drop");
  const filesInput = $("files");
  $("browse").addEventListener("click", () => filesInput.click());
  filesInput.addEventListener("change", () => upload(filesInput.files));
  ["dragenter", "dragover"].forEach(type =>
    drop.addEventListener(type, e => { e.preventDefault(); drop.classList.add("over"); }));
  ["dragleave", "drop"].forEach(type =>
    drop.addEventListener(type, e => { e.preventDefault(); drop.classList.remove("over"); }));
  drop.addEventListener("drop", e => upload(e.dataTransfer.files));

  async function upload(fileList) {
    if (!fileList || !fileList.length) return;
    const form = new FormData();
    [...fileList].forEach(file => form.append("files", file));
    log(`uploading ${fileList.length} file(s)...`);
    try {
      report(await api("/api/admin/ingest/files", { method: "POST", body: form }));
    } catch (err) { log("ERROR  " + err.message); }
    filesInput.value = "";
  }

  // ---------------------------------------------------------------- urls / text
  $("add-urls").addEventListener("click", async () => {
    const urls = $("urls").value.split("\n").map(u => u.trim()).filter(Boolean);
    if (!urls.length) return;
    log(`fetching ${urls.length} URL(s)...`);
    try {
      report(await api("/api/admin/ingest/urls", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ urls }),
      }));
      $("urls").value = "";
    } catch (err) { log("ERROR  " + err.message); }
  });

  $("add-text").addEventListener("click", async () => {
    const title = $("text-title").value.trim();
    const text = $("text-body").value.trim();
    if (!text) return;
    try {
      report(await api("/api/admin/ingest/text", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title, text }),
      }));
      $("text-title").value = "";
      $("text-body").value = "";
    } catch (err) { log("ERROR  " + err.message); }
  });

  $("reseed").addEventListener("click", async () => {
    if (!confirm("Rebuild the index from the seed corpus? Uploaded documents are dropped.")) return;
    log("rebuilding from seed corpus...");
    try {
      report(await api("/api/admin/reindex-seed", { method: "POST" }));
    } catch (err) { log("ERROR  " + err.message); }
  });
})();
