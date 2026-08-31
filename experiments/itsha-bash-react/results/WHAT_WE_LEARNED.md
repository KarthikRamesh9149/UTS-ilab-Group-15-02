# What we tweaked, what worked, what did not

Terminal-Bench only prints **1 or 0** for a whole task. Every agent run here got 0 because two (or more) hidden tests still failed. That 0 is not the result. **The result is which hidden tests passed after each harness change.**

The openssl task has 6 tests. That is the main comparison. Same model (`gpt-4o-mini`) unless it says otherwise.

---

## 1. Setup check (no model)

**Oracle** = Harbor runs the official human solution. Not an AI score.

- 5 tasks attempted
- **4 worked**, 1 timed out (`torch-tensor-parallelism` — this PC has no NVIDIA GPU)
- Meaning: Docker + Harbor + Terminal-Bench 2.1 work here. GPU tasks should stay out of a local subset.

---

## 2. Tweaks to the custom harness

The custom harness is a small loop: model writes a bash command → we run it in the container → we send the output back → repeat.

### Tweak A — v0.1: “just run whatever bash fence we see”

**What we tried:** Parse a ````bash` block and run it. If there were several blocks, take the first.

**Task:** `pypi-server` (build a Python package and serve it)

**What happened:** The model wrote a whole plan (mkdir, write files, build, start server). We only ran `mkdir`. Next turns forgot `cd` because each command is a new shell. It never built the package.

**Tests:** not a fair attempt — the loop was broken.

**Verdict: did not work.** A harness that drops all but the first command cannot be compared to Terminus-2.

---

### Tweak B — v0.2: one command per turn + remember the folder

**What we changed (only these):**

1. If the model sends **more than one** bash block, reject it and ask for a single command.
2. Remember the working directory (`cd` sticks).
3. If it writes `DONE` and a command in the same message, **run the command**, ignore DONE.

**Task:** `openssl-selfsigned-cert` (create a key, cert, pem, a text file, and a Python checker)

**Hidden tests with gpt-4o-mini:**

| Test | v0.2 custom | Terminus-2 (same model) |
|---|---|---|
| Directory `ssl/` exists | pass | pass |
| 2048-bit key, mode 600 | pass | pass |
| Certificate file | pass | pass |
| Combined `.pem` | pass | pass |
| `verification.txt` has the exact org/CN/date text | **fail** | **fail** |
| `check_cert.py` runs (no extra packages) | **fail** | **fail** |
| **Total** | **4 / 6** | **4 / 6** |

Both failed the same two things: the text file format was wrong, and the Python script did `import OpenSSL` (that package is not installed). The model stopped as if the task were finished.

**Tokens:** custom ~7.6k in / 0.6k out. Terminus-2 ~10k in / 1.4k out.

**Verdict: this tweak worked.** The loop now actually drives the model. On this task it **matched the established harness test-for-test**. Keep v0.2.

---

### Tweak C — v0.3: “don’t let it say DONE the first time”

**What we changed:** First `DONE` is refused. We tell the model to re-read the task and inspect files, then it may DONE.

**Same openssl task, same model:**

| | v0.2 | v0.3 |
|---|---|---|
| Tests passed | **4 / 6** | **4 / 6** (same two fails) |
| Tokens in | 7.6k | **33k** (~4×) |

It spent the extra turns fighting `sed` date formats. It never rewrote `check_cert.py` to drop `import OpenSSL`.

**Verdict: did not work.** More retries without a specific hint wasted tokens and did not pass another test. Drop v0.3. The running code is back to v0.2.

---

### Tweak D — same harness, weaker free model (v0.2.1 local)

**What we changed:** Nothing in the loop. Swapped gpt-4o-mini for local **Qwen2.5-Coder 1.5B** (Ollama, $0).

**Same openssl task:**

| Test | gpt-4o-mini + v0.2 | 1.5B + v0.2 |
|---|---|---|
| Directory | pass | pass |
| Key | pass | **fail** (tried a password-protected key) |
| Certificate | pass | fail |
| pem | pass | fail |
| verification.txt | fail | fail |
| Python script | fail | fail |
| **Total** | **4 / 6** | **1 / 6** |

The 1.5B model put many commands in one block, hung on a key passphrase, then said DONE.

**Verdict: the 4/6 was the stronger model, not a lucky container.** A 1.5B local model is too small for this task even with a working harness. $0, useful as a control.

---

## 3. Extra task: `fix-git` (custom v0.3, gpt-4o-mini)

| Test | Result |
|---|---|
| Layout file | pass |
| About file | fail |
| **Total** | **1 / 2** |

Terminus-2 on this task **does not count** — OpenRouter ran out of credit mid-run.

---

## 4. What to tell the group

**Worked**

- Harbor on this Windows PC (oracle 4/5 tasks).
- Forcing **one command per turn** and **sticky `cd`**. That is the only harness change that clearly improved behaviour.
- Custom v0.2 **tied Terminus-2** on openssl: **4/6 vs 4/6**, identical fails.

**Did not work**

- Taking only the first bash fence (v0.1).
- Vague “check your work before DONE” (v0.3) — 4× tokens, still 4/6.
- Local 1.5B Qwen — 1/6 on the same task.

**Do not keep doing**

- Paid OpenRouter until someone adds credit on purpose.
- Mixing these rows with Karthik’s 21-task 3B/7B matrix. Different models, different harness.

**Keep**

- Harness v0.2 (one command, sticky cwd).
- Report **tests passed / tests total**, not the official 0.
