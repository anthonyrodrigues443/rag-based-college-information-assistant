"""Draws the retrieval-accuracy chart for the deck from the measured eval results.

Reads data/eval/results.json so the slide can never drift from the numbers.
Writes data/eval/retrieval_chart.png at the aspect ratio of the deck's chart frame.
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "data" / "eval" / "results.json"
OUT = ROOT / "data" / "eval" / "retrieval_chart.png"

INK, TEAL, SEA, AMBER, MUTED, LINE = "#0B3B3C", "#028090", "#00A896", "#F4A259", "#5E7472", "#CFE3E1"
ORDER = [("bm25", "BM25\nonly"), ("dense", "Dense\nonly"),
         ("hybrid", "Hybrid\n(RRF fused)"), ("hybrid_rerank", "Hybrid +\nre-rank"),
         ("pipeline", "Shipped\npipeline")]


def main():
    data = json.loads(RESULTS.read_text())
    abl = data["ablation"]
    n = data["questions"]["answerable"]

    order = [(key, label) for key, label in ORDER if key in abl]
    labels = [label for _, label in order]
    hit1 = [abl[key]["hit1"] for key, _ in order]
    hit5 = [abl[key]["hit5"] for key, _ in order]

    fig, ax = plt.subplots(figsize=(6.0, 3.94), dpi=260)
    x = range(len(labels))
    width = 0.38
    bars1 = ax.bar([i - width / 2 for i in x], hit1, width, label="Hit@1", color=SEA)
    bars5 = ax.bar([i + width / 2 for i in x], hit5, width, label="Hit@5", color=TEAL)
    bars5[-1].set_color(AMBER)

    for group in (bars1, bars5):
        for bar in group:
            ax.annotate(f"{bar.get_height():.2f}",
                        (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                        ha="center", va="bottom", fontsize=7.5, color=INK,
                        fontfamily="DejaVu Sans")

    ax.set_title(f"Retrieval accuracy on {n} labelled questions",
                 fontsize=9.5, color=INK, pad=12)
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, fontsize=8, color=INK)
    ax.set_ylim(0, 1.26)
    ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.tick_params(axis="y", labelsize=7.5, colors=MUTED, length=0)
    ax.tick_params(axis="x", length=0)
    ax.yaxis.grid(True, color=LINE, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(LINE)
    legend = ax.legend(fontsize=8, frameon=False, loc="upper left", ncol=2,
                   bbox_to_anchor=(0.0, 1.0), handlelength=1.2)
    for text in legend.get_texts():
        text.set_color(INK)

    fig.tight_layout()
    fig.savefig(OUT, facecolor="white")
    print(f"wrote {OUT}")
    for (key, label), a, b in zip(order, hit1, hit5):
        print(f"  {label.replace(chr(10), ' '):<22} Hit@1 {a:.2f}   Hit@5 {b:.2f}")


if __name__ == "__main__":
    if not RESULTS.exists():
        sys.exit("run scripts/eval_full.py first")
    main()
