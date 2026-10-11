# Repo model comparison — checked 12 October 2026

The current `origin/main` result records at commit `7c50be31bc20425b94eab6e3ec3f28ebbf89da5b` use **DeepSeek V4 Flash 0731**, pinned through OpenRouter to DeepInfra FP8. The following counts were recomputed from the saved CSV task records and frozen development IDs, with no model calls.

| Harness | Distinct tasks with outcomes | Attempts | Passes | Verified failures | Development passes |
|---|---:|---:|---:|---:|---:|
| Custom C0-NC | 89 | 92 | 50 | 39 | 15 / 20 |
| Terminus-2 | 89 | 89 | 52 | 37 | 14 / 20 |
| OpenHands | 89 | 89 | 44 | 45 | 10 / 20 |

The custom result combines 89 original attempts with three separately recorded setup-recovery attempts. The original records retain three missing outcomes; the recovery-inclusive view has no missing outcomes. Recovery does not describe one uninterrupted 89-attempt run. Sources: [main results](https://github.com/KarthikRamesh9149/UTS-ilab-Group-15-02/tree/7c50be31bc20425b94eab6e3ec3f28ebbf89da5b/results) and [reporting implementation](https://github.com/KarthikRamesh9149/UTS-ilab-Group-15-02/blob/7c50be31bc20425b94eab6e3ec3f28ebbf89da5b/scripts/report_results.py).

The Gemini custom run attempted the same twenty development task IDs: **13 passes**, four verifier failures and three infrastructure failures, including two attempts with no official verifier score. Its native comparison has nine Terminus-2 attempts (seven passes) and nine OpenHands attempts (six passes). Twenty-two native attempts are unstarted.

The observed custom development comparison is therefore **DeepSeek 15/20 versus Gemini 13/20**. It does not establish a model-only ranking: harness versions, execution hosts, output ceilings, budgets and incomplete outcomes differ. Comparing Gemini's development percentage with DeepSeek's full-89 percentage would mix task sets. Current repo evidence does not establish that Gemini will beat DeepSeek.

The complete DeepSeek evaluation supports using it for the current project result. A future model comparison requires matched task IDs, frozen harness/settings and actual model-version verification. Gemini's version caveat is documented in [the preparation brief](BRIEF.md); no model was switched and no paid comparison was started during this review.
