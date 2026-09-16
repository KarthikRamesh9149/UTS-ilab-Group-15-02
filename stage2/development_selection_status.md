# Registered custom development selection

`development_selection.py` implements the approved selection rule without
launching trials or claiming a final win. It consumes complete, reaudited
20-task metadata blocks, rejects duplicates, wrong task/condition/protocol,
unverified cleanup, missing usage, invalid cost and missing runtime evidence.

Ranking is development passes descending, actual total API cost ascending,
implementation complexity ascending, then measured agent runtime ascending.
Complexity is the number of retained additions: planning and completion checks.
An otherwise exact tie uses the condition name deterministically.

C0/C1 select the parent. C2 must declare that selected parent, and its records
must agree. The final C0/C1/C2 winner determines the registered diagnostic:
ablate its retained addition with the largest positive incremental pass gain,
breaking equal-gain ties toward the later completion addition. Removing
planning from a C2-on-C1 winner retains completion checking on C0. If no retained
addition improves passes, repeat the winner unchanged. Diagnostic results must
remain separate from original selection results.

This is a pure tested decision function, not an executed development study.
The caller must freshly audit receipts and freeze the decision before the next
paid block. Finalist source/dependency freezing and the complete matrix driver
remain to be integrated. Seven synthetic tests cover ranking, ties, ablation,
repeat, completeness and parent rejection; they are not benchmark scores.
