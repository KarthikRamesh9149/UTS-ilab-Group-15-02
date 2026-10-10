"""Compare this branch's dev-20 runs with the project's Stage 2 reference runs.

    python results/harshini/compare_reference.py --refresh     # re-extract reference rows from origin/main
    uv run --no-project --with matplotlib python results/harshini/compare_reference.py

Reference rows come from these committed Stage 2 files on origin/main:
  stage2/results/baseline-corrected-20260923/trials.csv          (Terminus-2, OpenHands; round C)
  stage2/results/custom-no-cutoff-final-20260928/c0-nc/trials.csv (C0-NC, 89 tasks)
  stage2/results/custom-portable-20260926/c0/trials.csv           (C0, dev-20)
They are reduced to reference/stage2-reference-89.csv (one row per task). The script
prints the overlap and efficiency figures used in FINDINGS.md and draws dev20-tasks.png
and time-to-solve.png.
"""
from __future__ import annotations

import argparse
import csv
import io
import subprocess
from pathlib import Path
from statistics import median

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REF_CSV = HERE / "reference" / "stage2-reference-89.csv"
SOURCES = {
    "baseline": "stage2/results/baseline-corrected-20260923/trials.csv",
    "c0nc": "stage2/results/custom-no-cutoff-final-20260928/c0-nc/trials.csv",
    "c0": "stage2/results/custom-portable-20260926/c0/trials.csv",
}
HARNESSES = ("terminus2", "openhands", "c0nc")
METRICS = ("pass", "agent_s", "out_tokens", "in_tokens", "known_cost", "agent_error")


def dev20() -> list[str]:
    path = ROOT / "experiments" / "harshini-deepagents" / "dev20_tasks.txt"
    return [t.strip() for t in path.read_text(encoding="utf-8").splitlines() if t.strip() and not t.startswith("#")]


def git_csv(path: str) -> list[dict]:
    text = subprocess.run(["git", "show", f"origin/main:{path}"], cwd=ROOT, capture_output=True,
                          text=True, encoding="utf-8", check=True).stdout
    return list(csv.DictReader(io.StringIO(text)))


def reduce_row(row: dict) -> dict:
    return {
        "pass": "1" if row.get("reward") == "1" else "0",
        "agent_s": row.get("agent_seconds", ""),
        "out_tokens": row.get("output_tokens") or row.get("known_output_tokens", ""),
        "in_tokens": row.get("input_tokens") or row.get("known_input_tokens", ""),
        "known_cost": row.get("known_cost_usd", ""),
        "agent_error": row.get("agent_error_type", ""),
    }


def refresh() -> None:
    base = git_csv(SOURCES["baseline"])
    by = {"terminus2": {}, "openhands": {}}
    for row in base:
        key = "terminus2" if row["harness"] == "terminus-2" else "openhands"
        by[key][row["task_id"]] = reduce_row(row)
    by["c0nc"] = {row["task_id"]: reduce_row(row) for row in git_csv(SOURCES["c0nc"])}
    c0 = {row["task_id"]: row["reward"] == "1" for row in git_csv(SOURCES["c0"])}
    dev = set(dev20())
    fields = ["task", "dev20", "c0_pass"] + [f"{h}_{m}" for h in HARNESSES for m in METRICS]
    REF_CSV.parent.mkdir(exist_ok=True)
    with REF_CSV.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for task in sorted(by["terminus2"]):
            out = {"task": task, "dev20": "1" if task in dev else "0",
                   "c0_pass": ("1" if c0.get(task) else "0") if task in dev else ""}
            for h in HARNESSES:
                for m, v in by[h].get(task, {}).items():
                    out[f"{h}_{m}"] = v
            writer.writerow(out)
    print(f"wrote {REF_CSV.relative_to(ROOT)}")


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def report(ref: list[dict]) -> None:
    passed = {h: {r["task"] for r in ref if r[f"{h}_pass"] == "1"} for h in HARNESSES}
    tasks = {r["task"] for r in ref}
    union = passed["terminus2"] | passed["openhands"] | passed["c0nc"]
    print(f"89-task passes: " + ", ".join(f"{h} {len(passed[h])}" for h in HARNESSES))
    print(f"solved by at least one: {len(union)}; by none: {len(tasks - union)}; by all three: "
          f"{len(passed['terminus2'] & passed['openhands'] & passed['c0nc'])}")
    print(f"C0-NC only: {sorted(passed['c0nc'] - passed['terminus2'] - passed['openhands'])}")
    print(f"Terminus-2 only: {sorted(passed['terminus2'] - passed['c0nc'] - passed['openhands'])}")
    print(f"OpenHands only: {sorted(passed['openhands'] - passed['c0nc'] - passed['terminus2'])}")
    dev = {r["task"] for r in ref if r["dev20"] == "1"}
    held = tasks - dev
    print("dev-20 / other 69: " + ", ".join(f"{h} {len(passed[h] & dev)}/{len(passed[h] & held)}" for h in HARNESSES))
    for a, b in (("c0nc", "terminus2"), ("c0nc", "openhands"), ("terminus2", "openhands")):
        print(f"head-to-head {a} vs {b}: both {len(passed[a] & passed[b])}, only {a} {len(passed[a] - passed[b])}, "
              f"only {b} {len(passed[b] - passed[a])}, neither {len(tasks - passed[a] - passed[b])}")
    for h in HARNESSES:
        fails = [r for r in ref if r[f"{h}_pass"] != "1"]
        timeouts = sum(r[f"{h}_agent_error"] == "TimeoutError" for r in fails)
        print(f"{h}: {len(fails)} not passed, {timeouts} of them hit the agent time limit")
    for h in HARNESSES:
        wins = [r for r in ref if r[f"{h}_pass"] == "1"]
        med = lambda m: median([x for x in (num(r[f"{h}_{m}"]) for r in wins) if x is not None] or [0])
        total_in = sum(num(r[f"{h}_in_tokens"]) or 0 for r in ref)
        cost = sum(num(r[f"{h}_known_cost"]) or 0 for r in ref)
        print(f"{h}: median agent min per pass {med('agent_s') / 60:.1f}, median output tokens per pass "
              f"{med('out_tokens'):.0f}, known input tokens {total_in / 1e6:.1f}M, known cost ${cost:.2f}")


def plot(ref: list[dict]) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch, Rectangle

    def run(name):
        path = HERE / "deepagents" / f"{name}.csv"
        if not path.exists():
            return None
        with path.open(encoding="utf-8") as fh:
            return {r["task"]: r["status"] for r in csv.DictReader(fh)}

    ref_by = {r["task"]: r for r in ref}
    tasks = dev20()
    columns = [(f"Deep Agents\n0.1.3 run {i}\n(laptop)", data) for i, n in
               enumerate(("dev20-v0.1.3", "dev20-v0.1.3-r2", "dev20-v0.1.3-r3"), 1) if (data := run(n))]
    columns += [(f"Terminus-2\nrun {i}\n(laptop)", data) for i, n in
                enumerate(("dev20-terminus2-r1", "dev20-terminus2-r2", "dev20-terminus2-r3"), 1) if (data := run(n))]
    columns += [
        ("Terminus-2\nStage 2\n(server)", {t: "pass" if ref_by[t]["terminus2_pass"] == "1" else "fail" for t in tasks}),
        ("Stage 2\ncustom C0\n(server)", {t: "pass" if ref_by[t]["c0_pass"] == "1" else "fail" for t in tasks}),
    ]
    colours = {"pass": "#2e9e5b", "fail": "#d9534f", "error": "#f0ad4e", "not run": "#d5dbe1"}
    fig = plt.figure(figsize=(3.2 + 1.6 * len(columns), 8.4), dpi=160)
    ax = fig.add_axes([0.25, 0.09, 0.72, 0.78])
    for c, (label, data) in enumerate(columns):
        for r, task in enumerate(tasks):
            ax.add_patch(Rectangle((c + 0.06, r + 0.08), 0.88, 0.84, color=colours.get(data.get(task, "not run"), "#d5dbe1")))
        done = sum(data.get(t, "not run") != "not run" for t in tasks)
        score = sum(data.get(t) == "pass" for t in tasks)
        ax.text(c + 0.5, -0.3, f"{label}\n{score}/{done}" + ("" if done == len(tasks) else "\n(running)"),
                ha="center", va="bottom", fontsize=9, fontweight="bold", color="#1f3b5c")
    ax.set_xlim(0, len(columns))
    ax.set_ylim(len(tasks), -3.4)
    ax.set_yticks([r + 0.5 for r in range(len(tasks))])
    ax.set_yticklabels(tasks, fontsize=9)
    ax.set_xticks([])
    ax.tick_params(axis="y", length=0)
    for side in ax.spines.values():
        side.set_visible(False)
    fig.suptitle("dev-20 per task: Deep Agents and Terminus-2 on the laptop vs. Stage 2 server runs",
                 fontsize=12, fontweight="bold", color="#1f3b5c", y=0.99)
    fig.legend(handles=[Patch(color=colours["pass"], label="passed"), Patch(color=colours["fail"], label="failed"),
                        Patch(color=colours["error"], label="no score: provider overload (counted as failed)"),
                        Patch(color=colours["not run"], label="not run yet")],
               loc="lower center", ncol=4, frameon=False, fontsize=9, bbox_to_anchor=(0.6, 0.02))
    fig.savefig(HERE / "dev20-tasks.png", bbox_inches="tight", facecolor="white")
    print("wrote results/harshini/dev20-tasks.png")


def plot_time(ref: list[dict]) -> None:
    """Tasks solved within t minutes of agent time, all 89 tasks and the 69 not used for selection."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    style = {"c0nc": ("Stage 2 custom (C0-NC)", "#3a7bd5"), "terminus2": ("Terminus-2", "#1f3b5c"),
             "openhands": ("OpenHands", "#9aa5b1")}
    limits = list(range(0, 121))
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), dpi=160, sharey=False)
    for ax, (title, rows) in zip(axes, (("All 89 tasks", ref),
                                        ("69 tasks not used to select the custom harness",
                                         [r for r in ref if r["dev20"] != "1"]))):
        for h, (label, colour) in style.items():
            minutes = sorted(num(r[f"{h}_agent_s"]) / 60 for r in rows
                             if r[f"{h}_pass"] == "1" and num(r[f"{h}_agent_s"]) is not None)
            counts = [sum(m <= t for m in minutes) for t in limits]
            ax.step(limits, counts, where="post", color=colour, linewidth=2.2, label=f"{label} ({len(minutes)})")
        for t in (5, 10):
            ax.axvline(t, color="#ccc", linewidth=1, linestyle=":")
        ax.set_xscale("symlog", linthresh=10)
        ax.set_xticks([0, 2, 5, 10, 20, 30, 60, 120])
        ax.set_xticklabels(["0", "2", "5", "10", "20", "30", "60", "120"])
        ax.set_xlim(0, 120)
        ax.set_xlabel("Agent time allowed (minutes)")
        ax.set_title(title, fontsize=11, color="#1f3b5c")
        ax.grid(axis="y", color="#eee")
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
    axes[0].set_ylabel("Tasks solved")
    axes[0].legend(loc="upper left", frameon=False, fontsize=9)
    fig.suptitle("Tasks solved within a time budget — Stage 2 server runs, DeepSeek V4 Flash 0731 (one run each)",
                 fontsize=12, fontweight="bold", color="#1f3b5c")
    fig.text(0.01, 0.005, "Agent time per passed task as recorded; it includes waits on rate-limited requests, "
             "so it is indicative rather than a controlled speed test.", fontsize=8, color="#555")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(HERE / "time-to-solve.png", facecolor="white")
    print("wrote results/harshini/time-to-solve.png")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    if args.refresh or not REF_CSV.exists():
        refresh()
    with REF_CSV.open(encoding="utf-8") as fh:
        ref = list(csv.DictReader(fh))
    report(ref)
    for budget in (5, 10, 15, 30):
        for label, rows in (("all 89", ref), ("other 69", [r for r in ref if r["dev20"] != "1"])):
            counts = {h: sum(r[f"{h}_pass"] == "1" and (num(r[f"{h}_agent_s"]) or 1e9) <= budget * 60 for r in rows)
                      for h in HARNESSES}
            print(f"solved within {budget} min ({label}): " + ", ".join(f"{h} {n}" for h, n in counts.items()))
    try:
        plot(ref)
        plot_time(ref)
    except ImportError:
        print("matplotlib not installed; skipped the charts")


if __name__ == "__main__":
    main()
