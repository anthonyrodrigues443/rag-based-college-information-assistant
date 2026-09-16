(function () {
  const $ = id => document.getElementById(id);
  let token = sessionStorage.getItem("cq_token") || "";

  const api = async (path, options = {}) => {
    let response;
    try {
      response = await fetch(path, {
        ...options,
        headers: { "X-Admin-Token": token, ...(options.headers || {}) },
      });
    } catch (err) {
      throw new Error(`the server could not be reached (${err.message})`);
    }
    if (response.status === 401) throw new Error("Unauthorised. Check the admin token.");
    if (!response.ok) throw new Error(await response.text());
    return response.json();
  };

  const log = message => {
    const box = $("log");
    box.hidden = false;
    box.textContent = message + "\n" + box.textContent;
  };

  // Everything below comes out of documents staff did not write. It is put on the page
  // as text, never as markup, so metadata cannot run in the authenticated admin origin.
  const el = (tag, cls, text) => {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  };

  const cell = child => {
    const td = document.createElement("td");
    td.append(child);
    return td;
  };

  function renderStats(stats) {
    const box = $("stats");
    box.replaceChildren();
    [
      [stats.documents, "documents"],
      [stats.chunks, "chunks"],
      [stats.vectors, "vectors (384-d)"],
      [stats.seed_documents, "from seed corpus"],
      [stats.uploaded_documents, "uploaded"],
    ].forEach(([value, label]) => {
      const stat = el("div", "stat");
      stat.append(el("b", null, String(value ?? "")), el("span", null, label));
      box.append(stat);
    });
  }

  function renderDocs(docs) {
    $("doc-count").textContent = `(${docs.length})`;
    const tbody = $("docs");
    tbody.replaceChildren();
    docs.forEach(doc => {
      const row = document.createElement("tr");
      row.append(cell(document.createTextNode(doc.title || "")));
      row.append(cell(el("span", "tag", doc.kind || "page")));
      row.append(cell(el("span", "tag " + (doc.origin === "upload" ? "upload" : ""), doc.origin || "")));
      row.append(cell(document.createTextNode(String(doc.n_chunks ?? ""))));
      row.append(cell(document.createTextNode(
        String(doc.indexed_at || "").replace("T", " ").replace("+00:00", ""))));

      const button = el("button", "del", "remove");
      button.type = "button";
      button.dataset.id = doc.doc_id;
      button.setAttribute("aria-label", `Remove ${doc.title || "this document"} from the index`);
      button.addEventListener("click", () => remove(button, doc));
      row.append(cell(button));
      tbody.append(row);
    });
  }

  async function remove(button, doc) {
    if (!confirm(`Remove "${doc.title || "this document"}" from the index?`)) return;
    button.disabled = true;
    try {
      const data = await api("/api/admin/document/" + doc.doc_id, { method: "DELETE" });
      log(`removed ${data.removed_chunks} chunks`);
    } catch (err) {
      // The row still reflects the server, which still holds the document.
      log(`ERROR  could not remove ${doc.title || doc.doc_id} — ${err.message}`);
      button.disabled = false;
      return;
    }
    refresh();
  }

  async function refresh() {
    try {
      const data = await api("/api/admin/status");
      renderStats(data.stats);
      renderDocs(data.documents);
    } catch (err) {
      log("ERROR  could not read the index status — " + err.message);
    }
  }

  function report(payload) {
    payload.results.forEach(result => {
      if (result.skipped) {
        log(`SKIPPED  ${result.title} — ${result.skipped}`);
      } else {
        log(`INDEXED  ${result.title} — ${result.chunks} chunks, ${result.words || "?"} words`
          + (result.replaced ? " (replaced the previous version of this document)" : ""));
      }
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
    const submitted = $("urls").value;
    const urls = submitted.split("\n").map(u => u.trim()).filter(Boolean);
    if (!urls.length) return;
    log(`fetching ${urls.length} URL(s)...`);
    try {
      const payload = await api("/api/admin/ingest/urls", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ urls }),
      });
      report(payload);
      if ($("urls").value === submitted) {
        $("urls").value = urls.filter((url, i) => !payload.results[i]?.chunks).join("\n");
      }
    } catch (err) { log("ERROR  " + err.message); }
  });

  $("add-text").addEventListener("click", async () => {
    const submittedTitle = $("text-title").value;
    const submittedText = $("text-body").value;
    const title = submittedTitle.trim();
    const text = submittedText.trim();
    if (!text) return;
    try {
      const payload = await api("/api/admin/ingest/text", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title, text }),
      });
      report(payload);
      if (payload.results[0]?.chunks && $("text-title").value === submittedTitle
          && $("text-body").value === submittedText) {
        $("text-title").value = "";
        $("text-body").value = "";
      }
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
