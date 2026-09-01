# Numbers (tests passed, not official 0/1)

Official Terminal-Bench reward is 1 only if every hidden test passes. Agent runs below did not clear every test. Counts are hidden tests passed. Notes: [WHAT_WE_LEARNED.md](WHAT_WE_LEARNED.md).

## openssl-selfsigned-cert (6 tests) — main comparison

Same task. Custom harness vs Terminus-2 uses **gpt-4o-mini**. Local row uses **Qwen 1.5B**.

| Who | Tests passed | Which tests |
|---|---|---|
| Custom **v0.2** + gpt-4o-mini | **4 / 6** | dir, key, cert, pem. Failed: verification.txt format, Python `import OpenSSL` |
| **Terminus-2** + gpt-4o-mini | **4 / 6** | **same four passed, same two failed** |
| Custom v0.3 + gpt-4o-mini (force a review before DONE) | **4 / 6** | same two fails; ~4× tokens vs v0.2 |
| Custom v0.2 + local Qwen **1.5B** | **1 / 6** | directory only |

## Other runs

| Who | Task | Tests | Note |
|---|---|---|---|
| Oracle (official solution, no AI) | 5 mixed TB 2.1 tasks | **4 / 5** | GPU task timed out; setup works |
| Custom v0.1 + gpt-4o-mini | pypi-server | loop broken | only `mkdir` ran; not comparable |
| Custom v0.3 + gpt-4o-mini | fix-git | **1 / 2** | layout ok, about file failed |
| Terminus-2 + gpt-4o-mini | fix-git | — | OpenRouter credit error; ignore |

## Token cost of the openssl tweaks (gpt-4o-mini)

| Harness | Input tokens | Output tokens |
|---|---:|---:|
| v0.2 custom | 7,558 | 550 |
| v0.3 custom | 33,210 | 1,837 |
| Terminus-2 | 10,337 | 1,357 |
