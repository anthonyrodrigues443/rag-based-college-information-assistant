"""Builds image-only PDFs, the way a college scans a signed notice and uploads it.

These have no text layer at all, so the ingest pipeline has to fall back to OCR.
That is the point: it exercises the path that a text-extractable PDF never touches.
"""
import io
import json
import sys
from pathlib import Path

import fitz
from PIL import Image, ImageDraw, ImageFont

SEED = Path(__file__).resolve().parent.parent / "data" / "seed"
SEED.mkdir(parents=True, exist_ok=True)

W, H = 1654, 2339          # A4 at 200 dpi
MARGIN = 150

NOTICES = {
"convocation-schedule-scan": (
    "INSTITUTE OF ENGINEERING & TECHNOLOGY",
    "Notice: Convocation 2026 and collection of degree certificates",
    "Date: 08 August 2026",
    """The convocation ceremony for the graduating batch of 2026 will be held on
14 September 2026 at 10:00 in the main auditorium. Graduands must report by
09:00 for robing.

Degree certificates will be issued from the Examination Section, Room 210,
from 16 September 2026. A graduand who cannot attend the ceremony may collect
the certificate in person from 16 September 2026 between 11:00 and 16:00 on
working days.

Documents required at collection: the original identity card, the provisional
certificate, and a no dues clearance slip signed by the library and the
laboratory in charge. Collection by a representative requires an authorisation
letter with a copy of the graduand's photo identity.

The convocation fee is Rs. 1,500 and covers the certificate, the ceremony and
one guest pass. Additional guest passes are Rs. 300 each and are limited to two
per graduand. The fee is paid on the student portal under Examination,
Convocation, before 01 September 2026.

A duplicate degree certificate, if the original is lost, is issued against a
police complaint copy and a fee of Rs. 2,500, with an issue time of thirty
working days.""",
    "Controller of Examinations"),

"wifi-computer-centre-scan": (
    "INSTITUTE OF ENGINEERING & TECHNOLOGY",
    "Notice: Campus wifi and computer centre access rules",
    "Date: 04 August 2026",
    """Campus wifi access is granted against the student roll number for the
current academic year. The account is activated within two working days of
registration and stays active until the end of the even semester.

Each student is allowed two devices on the network at one time. A third device
is rejected automatically. Sharing credentials with another student leads to
suspension of the account for thirty days on the first instance.

The computer centre in the second floor of the library building is open from
09:00 to 19:00 on working days and from 09:00 to 13:00 on Saturdays. Printing
is charged at Rs. 2 per black and white page and Rs. 8 per colour page, paid
through the portal wallet.

Downloading of copyrighted material and running of servers or mining software
on the campus network is not permitted. The network team logs traffic and
reports violations to the discipline committee.

For a forgotten password or a blocked account, students may write to the
network administrator from the institute email address, or visit the computer
centre help desk between 11:00 and 16:00.""",
    "Head, Computer Centre"),
}


def font(size, bold=False):
    for path in ("/System/Library/Fonts/Supplemental/Times New Roman Bold.ttf" if bold
                 else "/System/Library/Fonts/Supplemental/Times New Roman.ttf",
                 "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold
                 else "/System/Library/Fonts/Supplemental/Arial.ttf",
                 "/Library/Fonts/Arial.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def wrap(draw, text, fnt, width):
    lines = []
    for para in text.split("\n\n"):
        words, line = para.replace("\n", " ").split(), ""
        for word in words:
            probe = f"{line} {word}".strip()
            if draw.textlength(probe, font=fnt) <= width:
                line = probe
            else:
                lines.append(line)
                line = word
        lines.append(line)
        lines.append("")
    return lines


def render(header, title, date, body, signature):
    image = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(image)
    y = MARGIN

    draw.text((MARGIN, y), header, fill="black", font=font(46, True)); y += 80
    draw.line((MARGIN, y, W - MARGIN, y), fill="black", width=3); y += 60
    for line in wrap(draw, title, font(38, True), W - 2 * MARGIN):
        draw.text((MARGIN, y), line, fill="black", font=font(38, True)); y += 52
    y += 10
    draw.text((MARGIN, y), date, fill="black", font=font(30)); y += 70

    for line in wrap(draw, body, font(32), W - 2 * MARGIN):
        draw.text((MARGIN, y), line, fill="black", font=font(32)); y += 46

    y += 60
    draw.text((W - MARGIN - 420, y), signature, fill="black", font=font(32, True))
    # a scan is never perfectly clean
    return image.rotate(0.35, resample=Image.BICUBIC, fillcolor="white")


META = {
    "convocation-schedule-scan": {
        "title": "Convocation 2026 and collection of degree certificates",
        "date": "2026-08-08", "kind": "circular", "source": "Circulars, scanned notice"},
    "wifi-computer-centre-scan": {
        "title": "Campus wifi and computer centre access rules",
        "date": "2026-08-04", "kind": "circular", "source": "Circulars, scanned notice"},
}


def build(name, parts):
    image = render(*parts)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=72)
    pdf = fitz.open()
    page = pdf.new_page(width=595, height=842)
    page.insert_image(fitz.Rect(0, 0, 595, 842), stream=buffer.getvalue())
    target = SEED / f"{name}.pdf"
    pdf.save(target)
    pdf.close()
    (SEED / f"{name}.meta.json").write_text(json.dumps(META[name], indent=2), encoding="utf-8")

    with fitz.open(target) as check:
        layer = check[0].get_text("text").strip()
    print(f"  {target.name}  ({target.stat().st_size//1024} KB, "
          f"text layer: {len(layer)} chars {'-> OCR required' if len(layer) < 40 else '!! HAS TEXT'})")


if __name__ == "__main__":
    print("building scanned notices:")
    for name, parts in NOTICES.items():
        build(name, parts)
    print("\nre-index with: ./.venv/bin/python -c \"from app.ingest import reindex_seed; reindex_seed()\"")
