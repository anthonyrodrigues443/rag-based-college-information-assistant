(function () {
  const title = document.getElementById("doc-title");
  const meta = document.getElementById("doc-meta");
  const link = document.getElementById("doc-link");
  const text = document.getElementById("doc-text");
  const error = document.getElementById("doc-error");

  const { longDate } = window.CQDates;

  function fail(message) {
    meta.hidden = true;
    error.hidden = false;
    error.textContent = message;
  }

  const id = decodeURIComponent(location.pathname.split("/").filter(Boolean).pop() || "");
  if (!id) {
    fail("No document was requested.");
    return;
  }

  fetch(`/api/site/document/${encodeURIComponent(id)}`)
    .then(response => {
      if (response.status === 404) throw new Error("This document is no longer in the index.");
      if (!response.ok) throw new Error(`The document could not be loaded (HTTP ${response.status}).`);
      return response.json();
    })
    .then(doc => {
      title.textContent = doc.title || "Source document";
      document.title = `${doc.title || "Source document"} · Institute of Engineering & Technology`;
      meta.textContent = [doc.source, doc.kind, longDate(doc.date)].filter(Boolean).join(" · ");
      if (/^https?:\/\//i.test(doc.url || "")) {
        const anchor = document.createElement("a");
        anchor.href = doc.url;
        anchor.rel = "noopener noreferrer";
        anchor.textContent = "Open the page this was indexed from";
        link.append(anchor);
        link.hidden = false;
      }
      text.textContent = doc.text || "";
      if (!doc.text) fail("This document has no readable text.");
    })
    .catch(err => fail(err.message));
})();
