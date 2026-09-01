# Bash-ReAct custom harness (Terminal-Bench 2.1)

Harbor agent that completes Terminal-Bench tasks by running **one shell command per turn**. The model is held fixed; only the harness changes.

Code and run notes: [`experiments/itsha-bash-react/`](experiments/itsha-bash-react/README.md)

## Comparison

| | Custom (v0.2) | Terminus-2 |
|---|---|---|
| Task | `openssl-selfsigned-cert` | same |
| Model | `gpt-4o-mini` | same |
| Hidden tests | **4 / 6** | **4 / 6** |
| Official reward | 0 | 0 |

Same two tests failed on both sides (`verification.txt` format; `check_cert.py` imported missing `OpenSSL`).
