# Custom Harness — Saranya

**Setup:** Docker + Harbor v0.22.0, Python 3.12 venv, Ollama running qwen2.5-coder:3b locally.

**Sanity check:** Oracle agent, 5/5 tasks passed — pipeline confirmed working.

## Custom Harness (`my-custom-agent` v0.1.0)

Built directly against Harbor's `BaseAgent` interface. Simple loop: send task + history to model → get one shell command → run it in sandbox → feed output back → repeat until "DONE" or 15 steps.

**Result (dna-assembly task, qwen2.5-coder:3b, local, $0 cost):**

| Metric | Value |
|---|---|
| Reward | 0.0 |
| Exceptions | 0 (clean run) |
| Input / Output tokens | 20,345 / 1,611 |
| Runtime | 1m 28s |

Task not solved, but a fully clean, complete, scored trial — no crashes.

## Comparison Attempt (mini-swe-agent, same model)

Tried running mini-swe-agent on the same local model for a same-model comparison. Failed with `NetworkConnectionError` — mini-swe-agent runs inside the Docker container and couldn't reach Ollama on the host, even with `host.docker.internal` and `--allow-agent-host`. Unresolved; likely a Docker networking config issue, not a code bug.

## Key issues hit and fixed along the way

- Gemini free-tier daily quota (20/day) exhausted twice → switched to local Ollama
- mini-swe-agent required a dummy API key even for local models

## Limitations

- Only one task run to completion — not a representative accuracy score
- No established-harness result on the same model yet (networking blocker)
- Harness not yet tested against the team's 20-task dev subset

## Next steps

- Fix container→host networking for local-model comparisons
- Run harness against the frozen 20-task subset
- Consider small paid Gemini credit to unblock cloud-model testing

Raw job logs and harness code included in this folder. See also `../saranya-exploration/` for the earlier Gemini-based debugging trail that preceded this work.
