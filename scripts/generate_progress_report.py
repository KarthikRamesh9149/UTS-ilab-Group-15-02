#!/usr/bin/env python3
"""Generate factual summary files from results.csv only."""
import csv
import json
import os
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]


def truth(value):
    return str(value).lower() == "true"


def summarize(rows):
    output = {}
    for harness in ("mini-swe-agent", "openhands"):
        group = [r for r in rows if r["harness"] == harness]
        valid = [r for r in group if truth(r["valid_trial"])]
        passed = [r for r in valid if truth(r["pass"])]
        infra = [r for r in group if truth(r["infrastructure_error"])]
        runtimes = [float(r["duration_seconds"]) for r in valid if r["duration_seconds"]]
        output[harness] = {
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
    lines = ["# Preliminary smoke-test summary", "", "Harness | Valid Trials | Passed | Failed | Infra Errors | Preliminary Pass Rate | Mean Runtime", "--- | ---: | ---: | ---: | ---: | ---: | ---:"]
    for harness, data in summary.items():
        rate = "unavailable" if data["preliminary_pass_rate"] is None else "%.1f%%" % (100 * data["preliminary_pass_rate"])
        lines.append("%s | %d | %d | %d | %d | %s | %s s" % (harness, data["valid_trials"], data["passed"], data["failed"], data["infrastructure_errors"], rate, fmt(data["mean_runtime_seconds"])))
    table = "\n".join(lines) + "\n"
    (run_dir / "results_table.md").write_text(table)
    (run_dir / "summary.md").write_text(table + "\nPass rates are preliminary values on this three-task engineering smoke subset only.\n")
    limitations = """# Limitations

- Only three of the 89 Terminal-Bench 2.1 tasks were attempted per harness.
- Tasks were selected for infrastructure validation using a fixed seed and successful Oracle checks, not representativeness.
- Only one trial per task was run (`k=1`).
- Qwen2.5-Coder-3B-Instruct is intentionally small.
- The results are not statistically meaningful and are not directly comparable with official leaderboard rows.
- Ollama's Q4_K_M quantisation may differ from the full Hugging Face checkpoint.
- Tool invocation support differs between Mini-SWE-Agent and OpenHands; native OpenHands tool calling was disabled.
- A full fixed-model evaluation remains future work.
"""
    (run_dir / "limitations.md").write_text(limitations)
    total_valid = sum(v["valid_trials"] for v in summary.values())
    total_passed = sum(v["passed"] for v in summary.values())
    issues = sorted({r["error_type"] for r in rows if r["error_type"]})
    issue_text = ", ".join(issues) if issues else "no recorded compatibility or infrastructure exceptions"
    progress = f"""## Preliminary implementation and evaluation

Harbor 0.22.0 and the 89-task Terminal-Bench 2.1 dataset were configured on an Apple M5 MacBook Air. Qwen2.5-Coder-3B-Instruct was hosted locally through Ollama 0.33.2 as the Q4_K_M `qwen2.5-coder:3b` package (digest `f72c60cabf62`, 3.1B parameters, 32,768-token context). Host and container checks confirmed that Ollama's OpenAI-compatible endpoint was reachable at the same local address used by both harnesses.

Mini-SWE-Agent and OpenHands were each assigned the same frozen three-task subset, deterministic temperature setting, model digest, context length, `k=1`, and concurrency of one. Across the six intended trial rows, {total_valid} produced valid verifier results and {total_passed} passed. Recorded compatibility or infrastructure statuses were: {issue_text}. Missing token fields remain unavailable rather than being reported as zero; local monetary API cost is zero because no paid endpoint was used.

The purpose of this run was to validate model serving, Harbor task resolution, harness installation, trajectory capture, verification, and result parsing. It is not a full benchmark estimate and must not be interpreted as Terminal-Bench 2.1 accuracy. Next steps are deployment on suitable HPC infrastructure, evaluation of a stronger fixed local model, a frozen 20-task engineering subset, and eventually a controlled 89-task evaluation with repeated trials.
"""
    (run_dir / "progress_report_section.md").write_text(progress)
    print("Generated factual summary and progress-report files in", run_dir)


if __name__ == "__main__":
    main()

