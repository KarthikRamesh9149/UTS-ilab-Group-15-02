# Development block execution

`run_development.py` implements explicit OpenHands, C0, C1 and C2 blocks on the
same frozen 20 tasks, after the first Terminus-2 block and its evidence-bound
systemic review clear the expansion gate. Each invocation runs one block only.

The runner enforces predecessor completion, exclusive matrix ownership,
current host admission, registered custom limits, durable block configuration,
fresh accounting checks, and no replay of completed reward-zero trials.
Interrupted attempts require inspection, not automatic retry. C2 inherits the
C0/C1 parent selected by the registered accuracy/cost/simplicity/runtime rule.
The finalist freeze now includes this runner and the qualification review code.

Unit tests use simulated trials and mocked admission; they are not model or
benchmark results. No paid development block was launched by this change.
Custom limits still require registration before C0. The current Mac remains
unqualified: the Rosetta reference run completed 20 tasks with 16 passes and
four failures, including three unsupported-syscall failures and one HTTP 403.
An approved compatible host and fresh qualification remain necessary.

The diagnostic block, final execution driver, and actual measured comparison
remain outstanding. These safeguards do not establish a custom-harness win.
