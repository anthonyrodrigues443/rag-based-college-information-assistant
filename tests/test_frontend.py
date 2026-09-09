"""The browser side.

The date formatters run under node, which needs no DOM. The rest are structural checks
that lock in the fixes verified by hand in Chromium: issue #1 (metadata rendered as
markup), #8 (citations reachable only by mouse), #9 (focus lost on close), #12, #13,
#18 and #19.
"""
import json
import shutil
import subprocess

import pytest

from app import config

STATIC = config.WEB_DIR / "static"
node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


# ------------------------------------------------------------------ date formatting
BAD_DATES = ["2026-13-01", "2026-00-10", "2026-02-30", "2026-02-29", "", "not a date",
             "2026/08/14", "20260814", "0000-00-00", None]


@node
def test_the_date_formatters_never_throw_on_bad_input():
    """Issue #14: longDate() indexed a month array without checking the month, so an
    invalid date took the whole answer down with it."""
    script = f"""
        require({str(STATIC / "dates.js")!r});
        const {{ shortDate, longDate }} = globalThis.CQDates;
        const bad = {json.dumps(BAD_DATES)};
        const out = {{ bad: bad.map(v => [shortDate(v), longDate(v)]),
                      good: [shortDate("2026-08-14"), longDate("2026-08-14")] }};
        console.log(JSON.stringify(out));
    """
    result = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)
    assert all(pair == ["", ""] for pair in data["bad"]), data["bad"]
    assert data["good"] == ["14 AUG 26", "14 August 2026"]


@node
@pytest.mark.parametrize("name", ["dates.js", "widget.js", "admin.js", "source.js"])
def test_the_scripts_parse(name):
    subprocess.run(["node", "--check", str(STATIC / name)], capture_output=True, check=True)


# ------------------------------------------------------------------ structure
def read(name):
    return (config.WEB_DIR / name).read_text(encoding="utf-8")


def test_citation_excerpts_are_a_button_not_a_click_handler_on_a_div():
    """Issue #8: a div with tabIndex -1 and a click listener is unreachable by keyboard."""
    widget = read("static/widget.js")
    assert 'el("button", "cq-cite-toggle")' in widget
    assert 'setAttribute("aria-expanded"' in widget
    assert 'setAttribute("aria-controls"' in widget
    assert "tabIndex = -1" not in widget


def test_closing_the_panel_returns_focus_to_the_launcher():
    """Issue #9."""
    widget = read("static/widget.js")
    close = widget[widget.index("function close()"):]
    assert "launcher.focus()" in close[:close.index("}")]


def test_the_notices_panel_has_a_failure_state_and_a_retry():
    """Issue #18: a failed request left the panel reading "Loading notices…" forever."""
    widget = read("static/widget.js")
    assert "noticesFailed" in widget
    assert '"Try again"' in widget


def test_the_admin_table_is_built_from_text_nodes():
    """Issue #1: doc.kind went through innerHTML, so metadata ran as script."""
    admin = read("static/admin.js")
    docs_section = admin[admin.index("function renderDocs"):admin.index("async function remove")]
    assert "innerHTML" not in docs_section
    assert "createTextNode" in docs_section


def test_no_admin_rendering_path_uses_innerhtml():
    assert "innerHTML" not in read("static/admin.js")


def test_a_failed_deletion_is_caught_and_logged():
    """Issue #19: the rejected fetch surfaced only in the browser console."""
    admin = read("static/admin.js")
    remove = admin[admin.index("async function remove"):admin.index("async function refresh")]
    assert "catch" in remove
    assert "could not remove" in remove


def test_the_admin_page_has_one_level_one_heading():
    """Issue #12."""
    admin = read("admin.html")
    assert admin.count("<h1") == 1
    assert "<h1 class=\"brand\"" in admin


def test_the_action_column_has_a_header():
    """Issue #13: the sixth column was declared as <th></th>."""
    assert "<th>Actions</th>" in read("admin.html")
    assert "<th></th>" not in read("admin.html")


def test_the_document_table_scrolls_inside_its_card():
    """Issue #17: six columns pushed the whole document wider than a phone viewport."""
    assert 'class="table-scroll"' in read("admin.html")
    assert ".table-scroll{overflow-x:auto}" in read("static/admin.css")


def test_repeated_landmarks_are_named_and_content_sits_inside_one():
    """Issue #11."""
    index = read("index.html")
    assert '<nav class="utility-links" aria-label="Utility">' in index
    assert '<nav class="mainnav" aria-label="Main">' in index
    assert '<section class="utility" aria-label="Site utilities">' in index
    assert '<section class="ticker" aria-label="Latest updates">' in index
    assert '<section class="hero" aria-labelledby="hero-heading">' in index
    assert 'class="col-left" aria-labelledby=' in index
    assert 'class="col-right" aria-labelledby=' in index


# ------------------------------------------------------------------ contrast
def luminance(colour):
    channels = [int(colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    channels = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def contrast(foreground, background):
    a, b = luminance(foreground), luminance(background)
    return (max(a, b) + 0.05) / (min(a, b) + 0.05)


# Every combination axe reported in issue #10, plus the two states it did not reach.
CONTRAST_CASES = [
    ("widget.css", ".cq-cite small", "#ffffff"),
    ("widget.css", ".cq-cite small", "#fafbfc"),      # the hover background
    ("widget.css", ".cq-meta", "#ffffff"),
    ("widget.css", ".cq-typing", "#f1f3f6"),
    ("admin.css", ".msg.good", "#ffffff"),
    ("admin.css", ".msg.good", "#f6f7f9"),
    ("site.css", ".crest", "#eceff3"),
]


def declared_colour(stylesheet, selector):
    import re
    css = (STATIC / stylesheet).read_text(encoding="utf-8")
    block = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", css)
    assert block, f"{selector} not found in {stylesheet}"
    colour = re.search(r"(?<![-\w])color:\s*(#[0-9a-fA-F]{6})", block.group(1))
    assert colour, f"no literal colour on {selector}"
    return colour.group(1).lower()


@pytest.mark.parametrize("stylesheet,selector,background", CONTRAST_CASES)
def test_small_text_meets_the_contrast_threshold(stylesheet, selector, background):
    ratio = contrast(declared_colour(stylesheet, selector), background)
    assert ratio >= 4.5, f"{selector} on {background} is {ratio:.2f}:1"
