# Custom harness changelog

Design lever changes only. Score moves get recorded when a task run finishes.

## 0.1.0 — 2026-08-31

- Minimum Harbor agent: one bash command per turn, markdown fence parser.
- No JSON schema, no inspect/edit/test phases, no evidence gate (those are the group-repo choices).
- 15-step cap, 4k observation clip, temperature 0.
- Model via OpenRouter (hosted), not local Ollama.
- Hypothesis: a weaker format (markdown vs JSON) may still work better on hosted 7B+ models because parse failures are cheaper to recover from than a broken JSON contract.

### Probe 2026-08-31 — `pypi-server` / `openai/gpt-4o-mini` / k=1

- Reward **0.0**, 56s, 12,945 in / 925 out tokens, 0 parse failures, 12 commands.
- Failure is harness design, not Harbor: parser keeps only the **first** ```bash fence, so a multi-command plan ran only `mkdir`. `cd` does not persist across `exec()` calls. Model also wrote `DONE` in the same turn as a command; v0 ignores DONE if a command is present.
- Next lever: one command per turn enforced, working directory sticky or documented, DONE only with empty command.

## 0.2.0 — 2026-08-31

- Reject replies with more than one bash fence (do not run the first command only).
- Sticky cwd: wrap each command in `cd $cwd`, then capture `pwd` after it.
- DONE is ignored if a command is also present.
- Default step budget 20. Prompt tells the model it already starts in the current directory.
- Same markdown format as 0.1.0 so this isolates control-loop levers, not JSON vs markdown.

### Probe — `openssl-selfsigned-cert` / gpt-4o-mini / v0.2.0

- Reward **0.0**, 45s, 7,558 in / 550 out. Loop was healthy: 8 commands, 0 parse failures.
- Verifier: 4 passed (dir, key, cert, pem), 2 failed (`verification.txt` date format; `check_cert.py` imported missing `OpenSSL`).
- Control-loop fix worked; remaining miss is premature DONE.

## 0.3.0 — 2026-08-31

- First DONE is denied once. Model must inspect artifacts against the instruction, then DONE is allowed.

### Probe — openssl v0.3 vs v0.2 vs Terminus-2

- v0.3 still **0.0** and still 4/6. Tokens 33k vs 7.5k. Did not convert.
- Terminus-2 on the same task/model: **0.0**, **4/6**, $0.0018. Same two failing tests.
- v0.2 is the keeper. v0.3 is a negative result (more cost, no score move).

## 0.2.1 — 2026-08-31

- Same loop as 0.2.0 (v0.3 review was removed from the running agent).
- Can talk to local Ollama (`OPENAI_BASE_URL=http://127.0.0.1:11434/v1`) so later probes cost $0.

### Probe — openssl / local `qwen2.5-coder:1.5b` / v0.2.1

- Reward **0.0**, 44s, $0, **1/6** tests (directory only).
- Model stuffed many commands into one fence, created a password-protected key, failed, then replied `DONE`.
- Same harness as the gpt-4o-mini 4/6 run, so the 4/6 was the stronger model, not a fluke.
