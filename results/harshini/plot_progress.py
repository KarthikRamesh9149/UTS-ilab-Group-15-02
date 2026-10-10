"""Draw results/harshini/progress.png: repeat-study runs on the laptop next to the
Stage 2 server reference scores (dev-20).

    uv run --no-project --with matplotlib python results/harshini/plot_progress.py
"""
from __future__ import annotations

import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

HERE = Path(__file__).resolve().parent
SERVER = [("OpenHands", 10), ("Terminus-2", 14), ("Stage 2 custom (C0)", 15)]
LAPTOP = [
    ("Terminus-2", ("dev20-terminus2-r1", "dev20-terminus2-r2", "dev20-terminus2-r3"), "#1f3b5c"),
    ("Deep Agents 0.1.3", ("dev20-v0.1.3", "dev20-v0.1.3-r2", "dev20-v0.1.3-r3"), "#2e9e5b"),
]
TARGET = 16


def score(name: str) -> int | None:
    path = HERE / "deepagents" / f"{name}.csv"
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as fh:
        return sum(r["status"] == "pass" for r in csv.DictReader(fh))


def main() -> None:
    rows = [(f"{h}\nNetcup server, 1 run", [s], "#9aa5b1") for h, s in SERVER]
    for harness, runs, colour in LAPTOP:
        scores = [s for s in map(score, runs) if s is not None]
        if scores:
            rows.append((f"{harness}\nWindows laptop, {len(scores)} runs", scores, colour))

    fig, ax = plt.subplots(figsize=(11, 5.2), dpi=160)
    fig.suptitle("dev-20 tasks passed — DeepSeek V4 Flash 0731, same model and settings everywhere",
                 fontsize=13, fontweight="bold", color="#1f3b5c")
    for y, (label, scores, colour) in enumerate(rows):
        mean = sum(scores) / len(scores)
        ax.barh(y, mean, color=colour, height=0.55, alpha=0.9)
        if len(scores) > 1:
            ax.plot([min(scores), max(scores)], [y, y], color="black", linewidth=1.5)
            ax.scatter(scores, [y] * len(scores), color="white", edgecolor="black", zorder=3, s=36)
            text = f"mean {mean:.1f}  (runs: {', '.join(map(str, scores))})"
        else:
            text = f"{scores[0]}/20"
        ax.text(max(scores) + 0.4, y, text, va="center", fontsize=10, fontweight="bold")
    ax.axhline(len(SERVER) - 0.5, color="#bbb", linewidth=1)
    ax.axvline(TARGET, color="#2e9e5b", linestyle="--", linewidth=1.5)
    ax.text(TARGET + 0.15, -0.6, f"target {TARGET}/20", color="#2e9e5b", fontsize=9, fontweight="bold")
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r[0] for r in rows], fontsize=9)
    ax.invert_yaxis()
    ax.set_xlim(0, 20)
    ax.set_xticks(range(0, 21, 2))
    ax.set_xlabel("Tasks passed out of 20")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.legend(handles=[Line2D([], [], marker="o", color="black", markerfacecolor="white", label="one run")],
              loc="lower right", frameon=False, fontsize=9)
    fig.text(0.01, 0.01, "Server scores: Stage 2 runs (one run each). Laptop: repeat study, harnesses "
             "alternated run by run. Deep Agents run 2 lost 6 tasks to provider overload (counted as failed).",
             fontsize=8, color="#555")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(HERE / "progress.png", facecolor="white")
    print("wrote results/harshini/progress.png")


if __name__ == "__main__":
    main()
