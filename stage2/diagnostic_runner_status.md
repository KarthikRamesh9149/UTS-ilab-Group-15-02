# Frozen diagnostic execution

The diagnostic runner consumes the existing finalist freeze. It executes only
the registered 20-task ablation or unchanged repeat, using separate trial IDs,
the development budget, identical model settings and registered custom limits.
It never reselects the finalist from diagnostic outcomes or dispatches final runs.

The runner checks the freeze and evidence-bound qualification before execution
and between trials. It shares the exclusive matrix lock and durable receipt
reaudit/resume logic. Existing failures are retained, incomplete attempts stop
execution, and a changed descriptor cannot silently restart the block.

Tests simulate execution and admission. No live API call or benchmark trial was
launched for this implementation. Compatible host qualification, actual paid
development, the real finalist freeze and final evaluation remain outstanding.
The diagnostic runner itself is included in the frozen implementation hashes.
