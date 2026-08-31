# Walkthrough: what we built, the code, how we ran it

Read this if the score table still feels abstract.

## Picture of one run

```
You (Windows PC)
    |
    |  harbor run ...
    v
Harbor starts a Docker box for one task (e.g. openssl)
    |
    |  "here is the task text"
    v
Our Python harness  (harness/v0_bash_agent.py)
    |
    |  asks the model: what command next?
    v
The model  (gpt-4o-mini or local Qwen)
    |
    |  replies with a ```bash command ```
    v
Harness runs that command INSIDE the Docker box
    |
    |  sends the output back to the model
    v
Repeat up to 12–20 times
    |
    v
Harbor runs hidden pytest tests on the files in the box
    |
    v
Each test is pass or fail. All must pass for official score = 1.
```

The **model** only writes text. The **harness** is the Python that talks to the model, extracts a command, and runs it. That Python file is the thing we are experimenting with.

---

## Exact commands we ran

Docker Desktop had to be running. Harbor was installed with `uv tool install harbor`.

### 1. Oracle (no AI) — “does Harbor even work?”

```powershell
harbor run -d terminal-bench/terminal-bench-2-1 -a oracle -l 5 -n 2 -o jobs --job-name report1-oracle-smoke -y
```

`-a oracle` = do not call a model; paste in the official solution.  
`-l 5` = first 5 tasks of the dataset.  
Result: **4 of 5 tasks fully passed**. One GPU training task timed out. So the machine and Harbor are fine.

### 2. Our harness v0.1 on `pypi-server` (gpt-4o-mini)

```powershell
harbor run -d terminal-bench/terminal-bench-2-1 `
  -a harness.v0_bash_agent:BashReActAgent `
  -m openai/gpt-4o-mini `
  -i terminal-bench/pypi-server `
  -n 1 -k 1 -o jobs --job-name v0-pypi-gpt4omini --yes --env-file .env
```

`-a harness.v0_bash_agent:BashReActAgent` means: import our class from `harness/v0_bash_agent.py`.  
`-m` is the model. `-i` is the task name. `-k 1` = try once.

### 3. Our harness v0.2 on `openssl-selfsigned-cert` (the good run)

Same idea, different job name: `v02-openssl-gpt4omini`.

### 4. Terminus-2 on the same openssl task (the baseline)

```powershell
harbor run -d terminal-bench/terminal-bench-2-1 `
  -a terminus-2 `
  -m openrouter/openai/gpt-4o-mini `
  -i terminal-bench/openssl-selfsigned-cert `
  -n 1 -k 1 -o jobs --job-name term2-openssl-gpt4omini --yes --env-file .env
```

Same task, same model, **their** harness instead of ours. That is the comparison.

### 5. Free local model (no OpenRouter)

```powershell
python harness/run_local.py openssl-selfsigned-cert
```

That script points the same Python harness at Ollama on `http://127.0.0.1:11434/v1` and model `qwen2.5-coder:1.5b`.

Raw logs for every run sit under `jobs/<job-name>/`. The file `agent/v0-trace.json` is a diary of every model reply and every command we actually ran.

---

## The harness code (the important bits)

File: `harness/v0_bash_agent.py`.

### What we tell the model (system prompt)

We do not let it chat freely. We tell it: one command per turn, in a bash fence.

```21:38:harness/v0_bash_agent.py
SYSTEM_PROMPT = """You are a terminal agent. Complete the task by running shell commands.

Rules:
- Think briefly, then emit exactly ONE bash command in a single fenced block.
...
Format:
<one or two sentences>
```bash
single command
```
"""
```

### How we turn the model’s text into a command (v0.2)

```107:119:harness/v0_bash_agent.py
    def parse_action(text: str) -> tuple[str | None, bool, str | None]:
        fences = [block.strip() for block in BASH_RE.findall(text or "") if block.strip()]
        done = bool(DONE_RE.search(text or ""))
        if len(fences) > 1:
            return None, False, "multiple_fences"
        if len(fences) == 1:
            command = fences[0]
            if command.upper() == "DONE":
                return None, True, None
            return command, False, "done_ignored" if done else None
        if done:
            return None, True, None
        return None, False, "no_command"
```

If there are **two** ````bash` blocks, we refuse. That is the v0.1 → v0.2 fix.

### How we remember `cd` (v0.2)

Each Harbor `exec` is a **new** shell. `cd folder` is forgotten unless we wrap it:

```128:135:harness/v0_bash_agent.py
    def _wrapped(self, command: str) -> str:
        return (
            f"cd {shlex.quote(self._cwd)} || exit 1\n"
            f"{command}\n"
            "status=$?\n"
            f"printf '\\n{CWD_MARK}%s\\n' \"$(pwd)\"\n"
            "exit $status\n"
        )
```

We `cd` to the last known folder, run the command, then print `__CWD__/the/new/path` so the next turn starts there.

### The loop

For each turn: call the model → parse → `environment.exec(...)` → append the output to the chat → repeat. That is `run()` in the same file.

---

## What v0.1 did wrong (real log)

Job: `jobs/v0-pypi-gpt4omini/.../v0-trace.json`

The model sent **six** bash blocks in one reply (mkdir, write files, build, serve, pip). v0.1 only executed the **first**:

```text
command actually run: mkdir -p vectorops && cd vectorops && ...
```

Then on the next turn the model thought the package was already built. `cd` had been forgotten. The package was never created. That is why v0.1 is not a real score.

---

## What v0.2 did right (real log)

Job: `jobs/v02-openssl-gpt4omini/.../v0-trace.json`

The model now sends **one** command per turn. We ran them in order:

1. `mkdir -p ssl`
2. `openssl genrsa -out ssl/server.key 2048 && chmod 600 ssl/server.key`
3. `openssl req -new -x509 ... -subj "/O=DevOps Team/CN=dev-internal.company.local"`
4. `cat ssl/server.key ssl/server.crt > ssl/server.pem`
5. write `verification.txt` (format ended up wrong)
6. write `check_cert.py` (used `import OpenSSL`, which is not installed)
7. `chmod +x check_cert.py`
8. `DONE`

Harbor then ran 6 hidden tests:

| Hidden test | v0.2 (ours) | Terminus-2 |
|---|---|---|
| folder `ssl/` | pass | pass |
| 2048-bit key, permissions 600 | pass | pass |
| certificate file | pass | pass |
| combined `.pem` | pass | pass |
| `verification.txt` has “DevOps Team” and dates as specified | fail | fail |
| `check_cert.py` runs with no extra packages | fail | fail |
| **Passed** | **4 / 6** | **4 / 6** |

Same two fails. That is “we tied the established harness on this task.”

---

## What v0.3 tried and why we dropped it

We added: the first time the model says DONE, ignore it and say “go inspect the files.”

It used **33k tokens** instead of **7.6k**. Tests stayed **4 / 6**. It looped on `sed` for dates and never fixed `import OpenSSL`. Extra retries without a specific hint did not help.

The code running now is **v0.2 again** (version string 0.2.1 only adds local Ollama support).

---

## Local 1.5B (same harness, weaker brain)

`python harness/run_local.py openssl-selfsigned-cert`

The tiny model put a whole script in **one** fence (password-protected key). That failed. Then it replied `DONE`. Tests: **1 / 6** (folder only).

So: **same Python harness, weaker model → fewer tests pass.** The 4/6 was gpt-4o-mini, not a fluke.

---

## What to keep saying in the report

1. We wrote a small Harbor agent in `harness/v0_bash_agent.py`.
2. We run it with `harbor run -a harness.v0_bash_agent:BashReActAgent ...`
3. One-command-per-turn + sticky `cd` is the change that mattered.
4. On openssl, that matched Terminus-2 at **4/6 tests**.
5. A vague DONE-retry and a 1.5B local model both did worse.
