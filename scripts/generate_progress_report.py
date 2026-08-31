#!/usr/bin/env python3
"""Generate factual summary files from results.csv only."""
import csv
import json
import os
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
MODELS = ("qwen2.5-coder:3b", "qwen2.5-coder:7b")
HARNESSES = ("mini-swe-agent", "openhands", "uts-qwen-harness")


def truth(value):
    return str(value).lower() == "true"


def summarize(rows):
    output = {}
    for model in MODELS:
        for harness in HARNESSES:
            group = [r for r in rows if r["harness"] == harness and r["model_name"] == model]
            valid = [r for r in group if truth(r["valid_trial"])]
            passed = [r for r in valid if truth(r["pass"])]
            infra = [r for r in group if truth(r["infrastructure_error"])]
            runtimes = [float(r["duration_seconds"]) for r in valid if r["duration_seconds"]]
            output[model + " | " + harness] = {
                "model": model, "harness": harness,
                "intended_trials": len(group), "valid_trials": len(valid), "passed": len(passed),
                "failed": len(valid) - len(passed), "infrastructure_errors": len(infra),
                "preliminary_pass_rate": (len(passed) / len(valid)) if valid else None,
                "mean_runtime_seconds": mean(runtimes) if runtimes else None,
            }
    return output


def fmt(value, digits=1):
    return "unavailable" if value is None else ("%.*f" % (digits, value))


def main():
    run_dir = Path(os.environ.get("RUN_DIR") or (ROOT / ".current_run").read_text().strip())
    with (run_dir / "results.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    summary = summarize(rows)
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    lines = ["# Fixed-subset comparison summary", "", "Model | Harness | Valid / Intended | Passed | Failed | Infra Errors | Pass Rate | Mean Runtime", "--- | --- | ---: | ---: | ---: | ---: | ---: | ---:"]
    for data in summary.values():
        rate = "unavailable" if data["preliminary_pass_rate"] is None else "%.1f%%" % (100 * data["preliminary_pass_rate"])
        lines.append("%s | %s | %d / %d | %d | %d | %d | %s | %s s" % (data["model"], data["harness"], data["valid_trials"], data["intended_trials"], data["passed"], data["failed"], data["infrastructure_errors"], rate, fmt(data["mean_runtime_seconds"])))
    table = "\n".join(lines) + "\n"
    (run_dir / "results_table.md").write_text(table)
    (run_dir / "summary.md").write_text(table + "\nPass rates are fixed-subset values from one trial on each of 21 tasks per condition.\n")
    limitations = """# Limitations

- A fixed 21-task subset of Terminal-Bench 2.1 was attempted; the full 89-task suite was intentionally out of scope.
- Tasks were selected deterministically using seed 42 and retained only after successful Oracle checks, so the subset is infrastructure-valid but not statistically representative.
- Only one trial per task was run (`k=1`).
- The two model sizes are compared only within this local setup and are not official leaderboard rows.
- Ollama's Q4_K_M quantisation may differ from the full Hugging Face checkpoint.
- Harness prompting and tool interfaces differ; OpenHands native tool calling was disabled for local endpoint compatibility.
- Oracle selection outcomes are separate from scored model trials and do not enter pass-rate calculations.
"""
    (run_dir / "limitations.md").write_text(limitations)
    total_valid = sum(v["valid_trials"] for v in summary.values())
    total_passed = sum(v["passed"] for v in summary.values())
    issues = sorted({r["error_type"] for r in rows if r["error_type"]})
    issue_text = ", ".join(issues) if issues else "no recorded compatibility or infrastructure exceptions"
    progress = f"""## Fixed-subset implementation and evaluation

Harbor 0.22.0 and Terminal-Bench 2.1 were configured on an Apple M5 MacBook Air. Qwen2.5-Coder-3B-Instruct and Qwen2.5-Coder-7B-Instruct were hosted locally through Ollama 0.33.2 as Q4_K_M packages (digests `f72c60cabf62` and `dae161e27b0e`) with a 32,768-token context. Host and container checks confirmed access to the same OpenAI-compatible local model service.

Mini-SWE-Agent, OpenHands, and custom UTS Qwen harness 2.2.0 were each assigned the same frozen 21-task subset for both model sizes, temperature zero, `k=1`, and concurrency one. Across 126 intended trial rows, {total_valid} produced valid verifier results and {total_passed} passed. Recorded compatibility or infrastructure statuses were: {issue_text}. Missing token fields remain unavailable rather than being reported as zero; no paid model endpoint was used.

This is a controlled local fixed-subset comparison, not a full Terminal-Bench 2.1 accuracy estimate. The full 89-task run was intentionally excluded from scope.
"""
    (run_dir / "progress_report_section.md").write_text(progress)
    print("Generated factual summary and progress-report files in", run_dir)


if __name__ == "__main__":
    main()
