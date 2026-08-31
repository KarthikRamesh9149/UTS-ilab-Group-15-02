# Fixed-subset comparison summary

Model | Harness | Valid / Intended | Passed | Failed | Infra Errors | Pass Rate | Mean Runtime
--- | --- | ---: | ---: | ---: | ---: | ---: | ---:
qwen2.5-coder:3b | mini-swe-agent | 21 / 21 | 0 | 21 | 0 | 0.0% | 353.5 s
qwen2.5-coder:3b | openhands | 21 / 21 | 0 | 21 | 0 | 0.0% | 442.9 s
qwen2.5-coder:3b | uts-qwen-harness | 20 / 21 | 0 | 20 | 0 | 0.0% | 233.2 s
qwen2.5-coder:7b | mini-swe-agent | 21 / 21 | 0 | 21 | 0 | 0.0% | 289.7 s
qwen2.5-coder:7b | openhands | 21 / 21 | 0 | 21 | 0 | 0.0% | 515.0 s
qwen2.5-coder:7b | uts-qwen-harness | 21 / 21 | 0 | 21 | 0 | 0.0% | 400.4 s

Pass rates are fixed-subset values from one intended trial on each of 21 tasks per condition. One custom-harness 3B trial ended on its 120-second command limit before verification and is retained as an invalid, non-infrastructure outcome.
