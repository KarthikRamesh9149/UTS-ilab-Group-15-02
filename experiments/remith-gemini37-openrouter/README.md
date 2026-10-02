# Remith Gemini 3.7 Flash via OpenRouter

Experiment owner: Remith

- Benchmark: Terminal-Bench 2.1
- Harnesses: Terminus-2 and OpenHands
- Model: `google/gemini-3.7-flash`
- Provider: OpenRouter
- Planned scope: fixed 20-task development subset
- Execution environment: Windows with Docker Desktop

This folder contains the setup notes, run protocol, and curated results for
this experiment. API keys and raw Harbor job directories must not be committed.

## Current Status

The infrastructure smoke test passed:

- Docker Desktop and the WSL2 backend were working.
- Harbor was installed through `uv` and upgraded from 0.22.0 to 0.23.0.
- The Oracle `build-pmars` smoke test completed with reward 1.0 and no exceptions.
- A direct, non-generative OpenRouter `/models` request confirmed that the
  professor-provided key can access `google/gemini-3.7-flash`.

No Gemini benchmark score has been recorded yet. Terminus-2, OpenHands, and a
branch-local custom harness all reached the OpenRouter endpoint but failed with
`401 Missing Authentication header` before the task agent produced work. The
failure is recorded as an execution/credential-propagation issue in the local
Harbor Windows trial path, not as a model-quality result.

## Attempt Log

| Attempt | Harness | Outcome |
| --- | --- | --- |
| Oracle smoke | Oracle | Passed, reward 1.0 |
| Terminus-2 smoke runs | Terminus-2 | Authentication header missing; no trial score |
| OpenHands setup smoke | OpenHands 0.61.0 | Setup succeeded, then authentication header missing |
| Custom OpenRouter smoke | `uts-gemini-openrouter-harness` | Authentication header missing; no trial score |

The fixed 20-task subset has **not** been run successfully. The experiment
must not report the failed 0.0 outcomes as benchmark accuracy. The next valid
run requires either Harbor hosted credential mode or a local proxy/runner that
injects the OpenRouter authorization header outside Harbor's failing boundary.

## Security and Reproducibility

- The API key is kept outside the repository in the local Windows user profile.
- Raw `jobs/` directories are local diagnostics only and must not be committed
  or uploaded.
- No credentials, model responses containing secrets, or private job metadata
  belong in this experiment folder.
- `scripts/openrouter_terminus.py` and
  `scripts/openrouter_custom_harness.py` are diagnostic branch-local adapters;
  they are not benchmark results.
