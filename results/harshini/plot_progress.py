"""Draw results/harshini/progress.png from the latest dev-20 CSV in deepagents/.

    uv run --no-project --with matplotlib python results/harshini/plot_progress.py
"""
from __future__ import annotations

import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Patch

HERE = Path(__file__).resolve().parent
BASELINES = [("OpenHands", 10, "#9aa5b1"), ("Terminus-2", 14, "#1f3b5c"), ("Stage 2 custom (C0)", 15, "#3a7bd5")]
TARGET = 16
COLOURS = {"pass": "#2e9e5b", "fail": "#d9534f", "error": "#f0ad4e", "unscored": "#f0ad4e", "not run": "#d5dbe1"}


def version_key(path: Path) -> tuple:
    tag = path.stem.split("-v", 1)[-1]
    return tuple(int(p) if p.isdigit() else 0 for p in tag.split("."))


def main() -> None:
    latest = max((HERE / "deepagents").glob("dev20-v*.csv"), key=version_key)
    rows = list(csv.DictReader(latest.open(encoding="utf-8")))
    passed = sum(r["status"] == "pass" for r in rows)
    finished = sum(r["status"] != "not run" for r in rows)
    complete = finished == len(rows)
    version = latest.stem.split("-v", 1)[-1]

    fig = plt.figure(figsize=(12, 5), dpi=160)
    fig.suptitle("Deep Agents harness vs. team baselines — DeepSeek V4 Flash, 20-task dev set",
                 fontsize=13, fontweight="bold", color="#1f3b5c", y=0.99)

    ax = fig.add_axes([0.09, 0.14, 0.47, 0.70])
    bars = list(BASELINES)
    if complete:
        bars.append((f"Deep Agents v{version}", passed, "#2e9e5b"))
    labels, scores, colours = zip(*bars)
    drawn = ax.barh(labels, scores, color=colours, height=0.55)
    for bar, score in zip(drawn, scores):
        ax.text(score + 0.3, bar.get_y() + bar.get_height() / 2, f"{score}/20",
                va="center", fontsize=11, fontweight="bold")
    ax.axvline(TARGET, color="#2e9e5b", linestyle="--", linewidth=2)
    ax.text(TARGET + 0.2, len(bars) - 0.55, f"target\n{TARGET}/20", color="#2e9e5b", fontsize=9, fontweight="bold")
    ax.set_xlim(0, 20)
    ax.set_xticks([0, 5, 10, 15, 20])
    ax.set_xlabel("Tasks passed out of 20")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)

    ax2 = fig.add_axes([0.62, 0.14, 0.36, 0.70])
    ax2.set_xlim(0, 5)
    ax2.set_ylim(0, 4.6)
    ax2.set_aspect("equal")
    ax2.axis("off")
    state = "complete" if complete else f"{finished} of {len(rows)} tasks finished"
    ax2.set_title(f"Latest run: v{version} ({state})\n{passed} passed", fontsize=11, color="#1f3b5c", loc="left")
    for i, row in enumerate(rows):
        x, y = 0.5 + i % 5, 3.9 - i // 5
        ax2.add_patch(Circle((x, y), 0.38, color=COLOURS.get(row["status"], "#d5dbe1")))
        ax2.text(x, y, str(i + 1), ha="center", va="center", fontsize=9,
                 color="white" if row["status"] != "not run" else "#555")
    ax2.legend(handles=[Patch(color=COLOURS["pass"], label="passed"), Patch(color=COLOURS["fail"], label="failed"),
                        Patch(color=COLOURS["not run"], label="not run yet")],
               loc="lower center", bbox_to_anchor=(0.5, -0.2), ncol=3, frameon=False, fontsize=9)

    fig.text(0.09, 0.02, "Reference scores: Netcup server. Deep Agents: Windows laptop host. "
             "Circle numbers follow dev20_tasks.txt order.", fontsize=8, color="#555")
    fig.savefig(HERE / "progress.png", bbox_inches="tight", facecolor="white")
    print(f"progress.png from {latest.name}: {passed}/{len(rows)} passed, {finished} finished")


if __name__ == "__main__":
    main()
