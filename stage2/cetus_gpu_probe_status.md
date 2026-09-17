# Local-model qualification: combined job queued

## Current status (supersedes inspection-only job below)

Job 89238 was confirmed still queued, then cancelled and replaced with
89247.hpc-head01. There is one combined qualification job: med_gpuq, two GPUs,
eight CPUs, 64 GB host memory, two-hour walltime. It runs
`cetus_local_probe.pbs` and `cetus_local_probe.py`.

The job verifies scheduler GPU allocation and minimum GPU memory; fetches all
four official Q4_K_M shards at revision b82fb7382639d97b38fa7672e526c760c2fb358e;
checks pinned SHA256 digests; builds llama.cpp revision
4bc272fd729bd094c0422e4b8353da8d2fec91f8 with installed GCC 13/CUDA 12.6; and
tests model loading, short generation, a synthetic tool call, and a bounded
long prompt. It configures a 32,768-token context but the prompt test is not
an exhaustive full-window capacity test. The service uses a Unix socket in a
private scratch directory, not an exposed TCP endpoint. No model-produced
commands or tools are executed. No external inference provider is used.

Model weights total 48,410,992,032 bytes. A 110 GiB scratch-free gate precedes
the download. Temporary files and model weights are retained for inspection
and potential reuse; the model process is stopped after the test. Download,
build, startup and request timeouts are bounded within the PBS allocation.
Three helper unit tests pass locally and under CETUS Python 3.6.8. Shell
syntax checks pass. None of these tests proves GPU runtime compatibility.

This is not yet a full combined Harbor qualification: Terminus-2, OpenHands
and custom scored execution are deliberately not launched because the task
networking/resource-isolation gates remain unresolved. The result explicitly
records `harbor_integration=not_tested` and `benchmark_trials=0`.

## Earlier inspection-only submission

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
