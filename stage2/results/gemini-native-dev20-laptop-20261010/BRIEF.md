# Gemini native comparison brief — 10 October 2026

The user selected up to twenty Terminus-2 and twenty OpenHands attempts on the frozen development subset, sharing the original US$20 experiment cap. Model, provider, reasoning and sampling settings remained fixed.

| Harness | Started / planned | Official scores | Official passes | Verifier failures | Infrastructure failures | Budget stops | Unstarted |
|---|---:|---:|---:|---:|---:|---:|---:|
| terminus-2 | 1 / 20 | 1 | 0 | 1 | 0 | 0 | 19 |
| openhands | 2 / 20 | 2 | 1 | 0 | 0 | 1 | 18 |

Official passes are actual verifier rewards; the failure/budget columns are classifications of attempts.

**Stop reason:** `budget_stop`.

## Spending

- New comparison known spending: **US$6.579041850**.
- Total experiment known spending, including original custom batch: **US$17.808674700**.
- Unresolved reservation from the original custom timeout: **US$1.10**. No new charges are unresolved.
- Conservative remaining allowance under the US$20 cap: **US$1.091325300**.
- New physical requests: **402**.
- An unresolved reservation is not a confirmed charge. Unfinished requests are never replayed automatically.

## Logging and setup

- 57 offline checks and both current-source native fake-provider Docker lifecycles passed before paid execution.
- Official task images, CPU/memory and agent/verifier deadlines were retained. Tasks requested no GPU; Gemini inference was remote.
- Langfuse Docker services were stopped during the batch to free RAM. Full private exchanges, native logs, tools and metadata were retained on disk.
- After restarting Langfuse, all **841 observations** across **3 paid** and **5 synthetic traces** were verified by observation ID.
- Langfuse's **402 paid generation observations** show the fixed Gemini model and exactly **US$6.579041850**, matching the closed ledger.
- The Windows backup matches all **2,839 private native files** by content hash. A private archive is retained; only its digest is published.
- Model access was revoked before verifier tests were uploaded. Container cleanup and any errors are recorded per attempt.
- Docker shared storage had no per-container disk quota; requested sizes are recorded rather than described as enforced.

## What can be concluded

The original custom batch remains 20 attempts, 18 official scores and 13 passes. These native results are a separate Gemini experiment. The native batch shared the remaining US$7.67 allowance, so missing cells and budget censoring must be exposed.

**0 tasks** have official scores from all three harnesses. The actual paired rewards are in comparison.json. A partial run does not establish superiority over the full twenty-task subset.

On the one completed native pair, **video-processing**, Terminus scored **0** and OpenHands scored **1**. Their costs were US$1.846329375 and US$4.691091225; agent runtimes were about 18.7 and 36.6 minutes. The original custom attempt on this task was unscored, so this is not a three-way comparison.

**build-pov-ray** started under OpenHands, then the budget guard denied further paid requests. Its official reward was 0; it is classified as a budget stop. The remaining 37 registered attempts were unstarted. US$1.091325300 of conservative headroom remained, less than the next required US$1.10 reservation.

No earlier DeepSeek score is used as Gemini comparison evidence. Credentials, task solutions, raw exchanges and private archives are excluded from Git.
