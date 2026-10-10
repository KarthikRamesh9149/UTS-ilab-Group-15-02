# Harshini Prasad — custom harness experiments (UTS iLab Project #15)

Branch `harshini-trial-run` of the UTS iLab Project #15 repository: building a custom
agent harness and comparing it with the client baselines on Terminal-Bench 2.1.

**Current work:** a LangGraph **Deep Agents** harness using **DeepSeek V4 Flash 0731**
(the model set by the client), compared against **Terminus-2** and **OpenHands**.

## Status

| | |
|---|---|
| Harness | Deep Agents, version 0.1.3 |
| Repeat study (done) | 3 dev-set runs each on the same Windows laptop, harnesses alternated |
| Deep Agents 0.1.3 | **10, 8, 11** of 20 — mean **9.7** |
| Terminus-2 (same laptop) | **11, 12, 11** of 20 — mean **11.3** |
| Reference scores | Terminus-2 14/20 and the Stage 2 custom harness (C0) 15/20, one run each on the Netcup server |

![Progress chart](results/harshini/progress.png)

Main results: a single dev-set run moves by up to 3 tasks between identical runs;
Terminus-2 is slightly ahead of this harness on the same host, but within that spread;
and the laptop host costs Terminus-2 about 3 tasks against the server.

**All findings:** [`results/harshini/FINDINGS.md`](results/harshini/FINDINGS.md) —
the repeat study, same-host vs. server comparison, where the Stage 2 harnesses differ,
and the harness bugs found on real tasks.

## Results by stage

### Stage 3 — Deep Agents harness, DeepSeek V4 Flash (October 2026, current)

Runs on the Windows laptop with Harbor and Docker; the model is called through OpenRouter
(DeepInfra FP8, the same route as the reference runs).

| Run | Harness | Tasks | Result | Notes |
|---|---|---|---|---|
| [`probe-openssl-v0.1.0`](results/harshini/deepagents/probe-openssl-v0.1.0.csv) | 0.1.0 | 1 | 0/1 (5 of 6 tests) | check script used a package the grader lacks |
| [`probe-openssl-v0.1.1`](results/harshini/deepagents/probe-openssl-v0.1.1.csv) | 0.1.1 | 1 | **1/1** | prompt fix: deliverables must use only preinstalled tools |
| [`dev20-v0.1.1`](results/harshini/deepagents/dev20-v0.1.1.csv) | 0.1.1 | 5 of 20 finished | **2 passed** | host went down; 2 failures were harness bugs |
| `dev20-v0.1.2` | 0.1.2 | 3 of 20 | no score | provider overload; all 3 ended on rate-limit errors (retry added in 0.1.3) |
| [`probe-openssl-terminus2`](results/harshini/deepagents/probe-openssl-terminus2.csv) | Terminus-2 | 1 | **1/1** | Terminus-2 with the reference settings runs on the laptop |
| [`dev20-v0.1.3`](results/harshini/deepagents/dev20-v0.1.3.csv) | 0.1.3 | 20 | **10/20** | repeat study run 1; both `qemu` tasks fail on this host |
| [`dev20-terminus2-r1`](results/harshini/deepagents/dev20-terminus2-r1.csv) | Terminus-2 | 20 | **11/20** | same laptop; also fails both `qemu` tasks (passed on Netcup) |
| [`dev20-v0.1.3-r2`](results/harshini/deepagents/dev20-v0.1.3-r2.csv) | 0.1.3 | 20 | **8/20** | 6 tasks lost to provider overload, counted as failed |
| [`dev20-terminus2-r2`](results/harshini/deepagents/dev20-terminus2-r2.csv) | Terminus-2 | 20 | **12/20** | |
| [`dev20-v0.1.3-r3`](results/harshini/deepagents/dev20-v0.1.3-r3.csv) | 0.1.3 | 20 | **11/20** | |
| [`dev20-terminus2-r3`](results/harshini/deepagents/dev20-terminus2-r3.csv) | Terminus-2 | 20 | **11/20** | |

Fixes between versions are listed in the
[harness changelog](experiments/harshini-deepagents/CHANGELOG.md).

**Reference scores** (same model, Netcup server):

| Harness | Dev 20 | Full 89 |
|---|---:|---:|
| Terminus-2 (client baseline) | 14 | 52 |
| OpenHands (client baseline) | 10 | 44 |
| Stage 2 custom harness (C0 / C0-NC) | 15 | 50 |

### Stage 2 — larger open model on UTS HPC (September 2026)

Qwen2.5-Coder-14B (AWQ) served with vLLM on the CETUS HPC, tasks run on the laptop over
an SSH tunnel, frozen 21-task subset.

| Check | Result |
|---|---|
| Oracle (official solutions) on the laptop | **21/21** tasks valid |
| Custom bash harness × 14B | **0/21** |
| mini-SWE-agent × 14B | not finished (4 of 21 trials, 0 passes) |

The model was too weak to pass any task, so this stage could not separate harnesses.
Details: [`results/harshini/README.md`](results/harshini/README.md).

### Stage 1 — team baseline with small local models (August 2026)

Qwen2.5-Coder 3B and 7B on three harnesses: **0 passes in all 126 trials**.
Archived write-up: [`docs/team-stage1.md`](docs/team-stage1.md).

## Next

1. Harness 0.1.4: when retries run out near the deadline, end the run so the grader still
   checks the task (removes the overload losses seen in run 2).
2. Single-lever tests (one change at a time, e.g. a file-layout completion check), each
   with repeated runs, since one run cannot show a 1–2 task effect.
3. Windows Oracle run of the tasks lost on this host (`qemu-*`, `adaptive-rejection-sampler`).
4. Add Langfuse tracing to the Deep Agents harness.

## Where things are

| Path | Contents |
|---|---|
| [`experiments/harshini-deepagents/`](experiments/harshini-deepagents/README.md) | Deep Agents harness, tests, task runner, changelog |
| [`results/harshini/deepagents/`](results/harshini/deepagents/) | one CSV per Deep Agents run |
| [`results/harshini/`](results/harshini/README.md) | Stage 2 results (Oracle, 14B runs) and the progress chart |
| [`experiments/itsha-bash-react/`](experiments/itsha-bash-react/README.md) | Stage 2 custom bash harness |
| [`hpc/`](hpc/) | CETUS PBS scripts for serving the Stage 2 model |
| [`docs/team-stage1.md`](docs/team-stage1.md) | archived team Stage 1 README |

Raw Harbor job folders (`jobs/`) are not committed. After a run:

```powershell
python experiments/harshini-deepagents/summarize_run.py dev20-v0.1.2 --dev20
uv run --no-project --with matplotlib python results/harshini/plot_progress.py
```
