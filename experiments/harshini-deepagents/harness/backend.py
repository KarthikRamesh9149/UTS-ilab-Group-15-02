"""Deep Agents sandbox backend that runs every operation inside the Harbor task container.

Deep Agents runs its built-in file tools (ls, read_file, edit_file, grep, glob) as
shell snippets through `execute`, so this one method is the whole contract.

Construct on the Harbor event loop. Deep Agents calls the sync methods from worker
threads, which marshal back onto that loop.
"""
from __future__ import annotations

import asyncio
import base64
import shlex
import time

from deepagents.backends.protocol import (
    ExecuteResponse,
    FileDownloadResponse,
    FileUploadResponse,
    WriteResult,
)
from deepagents.backends.sandbox import BaseSandbox

CWD_MARK = "__HARNESS_CWD__"
MAX_FILE_BYTES = 1024 * 1024


class Deadline:
    """Wall clock for one trial, shared by the backend and the prompt middleware."""

    def __init__(self, budget_seconds: float):
        self.budget = float(budget_seconds)
        self.started = time.monotonic()

    def remaining(self) -> float:
        return max(0.0, self.budget - (time.monotonic() - self.started))


class HarborShellBackend(BaseSandbox):
    def __init__(
        self,
        environment,
        deadline: Deadline,
        *,
        identifier: str,
        start_cwd: str = "/app",
        default_timeout: int = 300,
        max_output_chars: int = 12000,
    ):
        self.environment = environment
        self.deadline = deadline
        self._id = identifier
        self.cwd = start_cwd
        self.default_timeout = int(default_timeout)
        self.max_output_chars = int(max_output_chars)
        self.loop = asyncio.get_running_loop()
        self.last_exit_code: int | None = None
        self.commands_run = 0
        self.timeouts = 0

    @property
    def id(self) -> str:
        return self._id

    def _sync(self, factory):
        if self.loop.is_closed() or not self.loop.is_running():
            raise RuntimeError("Harbor event loop is unavailable")
        try:
            active = asyncio.get_running_loop()
        except RuntimeError:
            active = None
        if active is self.loop:
            raise RuntimeError("Use async backend methods on the Harbor event loop")
        return asyncio.run_coroutine_threadsafe(factory(), self.loop).result()

    def _clip(self, text: str) -> tuple[str, bool]:
        if len(text) <= self.max_output_chars:
            return text, False
        half = self.max_output_chars // 2
        dropped = len(text) - self.max_output_chars
        return (
            text[:half] + f"\n...[{dropped} chars truncated by harness]...\n" + text[-half:],
            True,
        )

    def _budget(self, timeout: int | None) -> int:
        # Leave headroom so the agent can still react before Harbor's own deadline.
        left = int(self.deadline.remaining()) - 20
        requested = self.default_timeout if timeout is None else int(timeout)
        return max(5, min(requested, left))

    async def _raw(self, command: str, timeout_sec: int):
        return await self.environment.exec(command, timeout_sec=timeout_sec)

    async def aexecute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse:
        seconds = self._budget(timeout)
        inner = (
            f"cd {shlex.quote(self.cwd)} 2>/dev/null || cd /\n"
            f"{command}\n"
            "__harness_status=$?\n"
            f"printf '\\n{CWD_MARK}%s\\n' \"$(pwd)\"\n"
            "exit $__harness_status\n"
        )
        # `timeout` kills the process group inside the container; Harbor's
        # timeout_sec is only the transport bound around it.
        wrapped = f"timeout -k 5 {seconds} bash -c {shlex.quote(inner)} 2>&1"
        try:
            result = await self._raw(wrapped, seconds + 30)
            output = (result.stdout or "") + (result.stderr or "")
            code = result.return_code
        except Exception as exc:  # Harbor transport timeout or exec failure
            output, code = f"[harness] command did not return: {type(exc).__name__}", 124
        if CWD_MARK in output:
            output, tail = output.rsplit(CWD_MARK, 1)
            new_cwd = tail.strip().splitlines()[0].strip() if tail.strip() else ""
            if new_cwd.startswith("/"):
                self.cwd = new_cwd
        self.commands_run += 1
        self.last_exit_code = code
        if code == 124:
            self.timeouts += 1
            output += (
                f"\n[harness] killed after {seconds}s. For long jobs, run them in the "
                "background (nohup CMD > /tmp/job.log 2>&1 &) and poll the log."
            )
        clipped, truncated = self._clip(output.rstrip())
        return ExecuteResponse(
            output=f"{clipped}\n[cwd={self.cwd} exit={code}]",
            exit_code=code,
            truncated=truncated,
        )

    def execute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse:
        return self._sync(lambda: self.aexecute(command, timeout=timeout))

    # Deep Agents' default write preflight shells out to python3, which some task
    # images lack. Creating the parent directory needs only coreutils.
    async def _awrite_preflight(self, file_path: str):
        response = await self._raw(f"mkdir -p -- \"$(dirname -- {shlex.quote(file_path)})\"", 30)
        if response.return_code != 0:
            return WriteResult(error=f"Failed to create parent directory for '{file_path}'")
        return None

    def _write_preflight(self, file_path: str):
        return self._sync(lambda: self._awrite_preflight(file_path))

    async def aupload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        results = []
        for path, content in files:
            if len(content) > MAX_FILE_BYTES:
                results.append(FileUploadResponse(path, error="file_size_limit"))
                continue
            error = None
            for offset in range(0, max(1, len(content)), 16384):
                chunk = base64.b64encode(content[offset:offset + 16384]).decode()
                op = ">" if offset == 0 else ">>"
                cmd = f"printf %s {shlex.quote(chunk)} | base64 -d {op} {shlex.quote(path)}"
                response = await self._raw(cmd, 30)
                if response.return_code != 0:
                    error = "container_write_failed"
                    break
            results.append(FileUploadResponse(path, error=error))
        return results

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        return self._sync(lambda: self.aupload_files(files))

    async def adownload_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        results = []
        for path in paths:
            cmd = f"head -c {MAX_FILE_BYTES + 1} {shlex.quote(path)} | base64 -w0"
            response = await self._raw(cmd, 30)
            if response.return_code != 0:
                results.append(FileDownloadResponse(path, error="container_read_failed"))
                continue
            data = base64.b64decode(response.stdout or "")
            if len(data) > MAX_FILE_BYTES:
                results.append(FileDownloadResponse(path, error="file_size_limit"))
            else:
                results.append(FileDownloadResponse(path, content=data))
        return results

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        return self._sync(lambda: self.adownload_files(paths))

    def stats(self) -> dict:
        return {
            "commands_run": self.commands_run,
            "command_timeouts": self.timeouts,
            "last_exit_code": self.last_exit_code,
            "final_cwd": self.cwd,
        }
