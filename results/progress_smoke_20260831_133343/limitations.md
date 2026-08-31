# Limitations

- A fixed 21-task subset of Terminal-Bench 2.1 was attempted; the full 89-task suite was intentionally out of scope.
- Tasks were selected deterministically using seed 42 and retained only after successful Oracle checks, so the subset is infrastructure-valid but not statistically representative.
- Only one trial per task was run (`k=1`).
- The two model sizes are compared only within this local setup and are not official leaderboard rows.
- Ollama's Q4_K_M quantisation may differ from the full Hugging Face checkpoint.
- Harness prompting and tool interfaces differ; OpenHands native tool calling was disabled for local endpoint compatibility.
- Oracle selection outcomes are separate from scored model trials and do not enter pass-rate calculations.
- One custom-harness 3B trial ended when an agent-selected command exceeded the frozen 120-second command limit. It produced no verifier result and is retained as an invalid, non-infrastructure outcome without retry.
