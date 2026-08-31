#!/usr/bin/env python3
"""Export reproducible terminal-style text and SVG evidence from results.csv."""
import csv
import html
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONDITIONS = (
    ("qwen2.5-coder:3b", "mini-swe-agent"),
    ("qwen2.5-coder:3b", "openhands"),
    ("qwen2.5-coder:3b", "uts-qwen-harness"),
    ("qwen2.5-coder:7b", "mini-swe-agent"),
    ("qwen2.5-coder:7b", "openhands"),
    ("qwen2.5-coder:7b", "uts-qwen-harness"),
)
TASK_ORDER = {
    task: index
    for index, task in enumerate(
        line.strip()
        for line in (ROOT / "configs/progress_subset.txt").read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )
}


def truth(value):
    return str(value).lower() == "true"


def terminal_lines(model, harness, rows):
    selected = [r for r in rows if r["model_name"] == model and r["harness"] == harness]
    selected.sort(key=lambda row: TASK_ORDER.get(row["task_id"], 999))
    lines = [
        "$ uts-bench results --model %s --harness %s" % (model, harness),
        "Terminal-Bench 2.1 | fixed subset | k=1 | temperature=0 | concurrency=1",
        "",
        "#   TASK                                      REWARD  VALID  INFRA  DURATION",
    ]
    for index, row in enumerate(selected, 1):
        reward = row["reward"] if row["reward"] != "" else "-"
        duration = ("%ss" % round(float(row["duration_seconds"]))) if row["duration_seconds"] else "-"
        lines.append(
            "%02d  %-40s %6s  %-5s  %-5s  %8s"
            % (index, row["task_id"][:40], reward, row["valid_trial"], row["infrastructure_error"], duration)
        )
    valid = [r for r in selected if truth(r["valid_trial"])]
    passed = [r for r in valid if truth(r["pass"])]
    infra = [r for r in selected if truth(r["infrastructure_error"])]
    rate = "%.1f%%" % (100 * len(passed) / len(valid)) if valid else "unavailable"
    lines += [
        "",
        "SUMMARY intended=%d valid=%d passed=%d failed=%d infra=%d pass_rate=%s"
        % (len(selected), len(valid), len(passed), len(valid) - len(passed), len(infra), rate),
        "SOURCE  results.csv (generated; no rows hand-edited)",
    ]
    return lines


def write_svg(path, lines):
    width = 1500
    line_height = 28
    height = 70 + line_height * len(lines)
    text_nodes = []
    for index, line in enumerate(lines):
        color = "#7ee787" if index == 0 else ("#58a6ff" if line.startswith("SUMMARY") else "#e6edf3")
        text_nodes.append(
            '<text x="34" y="%d" fill="%s">%s</text>'
            % (55 + index * line_height, color, html.escape(line))
        )
    svg = """<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">
<rect width="100%%" height="100%%" rx="14" fill="#0d1117"/>
<circle cx="22" cy="20" r="6" fill="#ff5f56"/><circle cx="42" cy="20" r="6" fill="#ffbd2e"/><circle cx="62" cy="20" r="6" fill="#27c93f"/>
<g font-family="SFMono-Regular,Menlo,Monaco,Consolas,monospace" font-size="18">%s</g>
</svg>\n""" % (width, height, width, height, "".join(text_nodes))
    path.write_text(svg)


def main():
    run_dir = Path(os.environ.get("RUN_DIR") or (ROOT / ".current_run").read_text().strip())
    with (run_dir / "results.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    output_dir = run_dir / "terminal_evidence"
    output_dir.mkdir(exist_ok=True)
    for model, harness in CONDITIONS:
        stem = "%s__%s" % (model.rsplit(":", 1)[-1], harness)
        lines = terminal_lines(model, harness, rows)
        (output_dir / (stem + ".txt")).write_text("\n".join(lines) + "\n")
        write_svg(output_dir / (stem + ".svg"), lines)
    print("Wrote %d terminal evidence pairs to %s" % (len(CONDITIONS), output_dir))


if __name__ == "__main__":
    main()
