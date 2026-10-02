# Remith Gemini OpenRouter Run Log

Owner: Remith  
Benchmark: Terminal-Bench 2.1  
Development task used for smoke tests: `terminal-bench/build-pmars`  
Planned evaluation: fixed 20-task subset  

## Environment

- Windows PowerShell
- Docker Desktop with WSL2 backend
- Harbor installed through `uv`
- Harbor upgraded from 0.22.0 to 0.23.0
- Model endpoint: OpenRouter
- Model: `google/gemini-3.7-flash`

## Confirmed Runs

| Run | Agent | Result | Interpretation |
| --- | --- | --- | --- |
| Oracle smoke | Oracle | Reward 1.0, 0 exceptions | Docker, Harbor, task image, and verifier worked |
| Terminus-2 smokes | Terminus-2 | 401 missing authentication header | No model task was evaluated |
| OpenHands v1 | OpenHands latest setup | Setup failure: missing `openhands.core` | No model task was evaluated |
| OpenHands v2/v3 | OpenHands 0.61.0 | 401 missing authentication header | Agent started, but no task work was completed |
| Custom OpenRouter smokes | Branch-local custom harness | 401 missing authentication header | No model task was evaluated |

## Findings

The direct OpenRouter `/models` request succeeded and showed access to
`google/gemini-3.7-flash`. The repeated Harbor trials failed before agent work
because the authorization header was absent at the OpenRouter request. These
are infrastructure/credential-propagation failures, not model-quality scores.

The 20-task subset has not been run successfully. No failed `0.0` smoke result
should be reported as Gemini accuracy.

## Reproduction Notes

Raw commands and Harbor job directories remain local diagnostics under `jobs/`.
They are intentionally excluded from this experiment folder and must not be
committed or uploaded.
