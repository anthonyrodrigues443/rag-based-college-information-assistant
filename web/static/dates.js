// Dates reach the page from documents nobody validated. A month of 13, a missing value
// or free text must format to nothing, never throw: a formatting failure would take the
// answer it belongs to down with it.
(function (root) {
  const SHORT = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"];
  const LONG = ["January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"];
  const ISO = /^(\d{4})-(\d{2})-(\d{2})$/;

  function parts(iso) {
    const match = ISO.exec(String(iso == null ? "" : iso).trim());
    if (!match) return null;
    const [, year, month, day] = match;
    const m = Number(month);
    const d = Number(day);
    // Round-tripping through the calendar rejects 30 February and 29 February in a year
    // that has no 29th, which a range check on its own would let through.
    const when = new Date(Date.UTC(Number(year), m - 1, d));
    if (when.getUTCFullYear() !== Number(year) || when.getUTCMonth() !== m - 1
        || when.getUTCDate() !== d) return null;
    return { year, month: m, day: d };
  }

  function shortDate(iso) {
    const p = parts(iso);
    return p ? `${String(p.day).padStart(2, "0")} ${SHORT[p.month - 1]} ${p.year.slice(2)}` : "";
  }

  function longDate(iso) {
    const p = parts(iso);
    return p ? `${p.day} ${LONG[p.month - 1]} ${p.year}` : "";
  }

  root.CQDates = { shortDate, longDate };
})(typeof globalThis !== "undefined" ? globalThis : this);
