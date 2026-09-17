# Local-model qualification: GPU inspection queued

17 September 2026: submitted PBS job 89238.hpc-head01 through hpc-login01.
Script: `cetus_gpu_inspect.pbs`. Request: med_gpuq, one GPU, two CPUs, 4 GB RAM,
three-minute walltime. This is hardware/driver inspection, not inference.

The scheduler accepted the job but reports state Q and:
`Not Running: Insufficient amount of resource: Qlist`.
No GPU model, VRAM, driver or model-loading success has yet been observed
inside this allocation. No OpenRouter credit has been spent. No compute work
was moved onto the login node or another user's allocation to avoid the queue.

The official Qwen3-Coder-Next Q4_K_M directory lists approximately 48.4 GB
of weights. File size is not total runtime VRAM; KV cache and runtime buffers
need additional capacity. Two confirmed 48 GB GPUs remain a candidate for
qualification, not a proven deployment or a claim of best benchmark accuracy.

Source:
https://huggingface.co/Qwen/Qwen3-Coder-Next-GGUF/tree/main/Qwen3-Coder-Next-Q4_K_M

Next steps after the job completes:
1. Inspect its log and exit status; verify device selection supplied by PBS.
2. Select a compatible, pinned inference runtime from the observed GPU/driver.
3. Reserve an appropriate GPU allocation for a bounded model-loading and
   synthetic generation test. Do not use devices outside that allocation.
4. Test context capacity, tool-call parsing and latency before model selection
   is frozen. Keep this local-model track separate from OpenRouter results.

Task networking, resource containment and Harbor runtime qualification remain
separate unresolved gates. A model-loading success does not resolve them.
