"""Per-trial background command handles; execution and signals stay in the container."""
import asyncio
import shlex
import uuid


class ContainerJobs:
    def __init__(self, backend):
        self.backend = backend
        self.jobs = {}

    async def start(self, command, timeout_seconds=60):
        if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 3600:
            raise ValueError('Timeout must be an integer between 1 and 3600 seconds')
        if len(self.jobs) >= 64 or sum(not task.done() for task, _ in self.jobs.values()) >= 4:
            raise ValueError('Per-trial command handle limit reached')
        if not isinstance(command, str) or not command.strip() or '\x00' in command:
            raise ValueError('Nonempty command required')
        identifier = uuid.uuid4().hex
        pid_path = '/tmp/uts-command-' + identifier + '.pgid'
        prefix = 'python3 -c ' + shlex.quote('import os; print(os.getpgrp())') + ' > ' + shlex.quote(pid_path)
        task = asyncio.create_task(self.backend.aexecute(prefix + ' && ' + command, timeout=timeout_seconds))
        self.jobs[identifier] = (task, pid_path)
        return {'job_id': identifier, 'status': 'started'}

    def poll(self, identifier):
        task, _ = self.jobs[identifier]  # unknown model-supplied handles fail closed
        if not task.done():
            return {'job_id': identifier, 'status': 'running'}
        result = task.result()  # transport failures must not become task success
        return {'job_id': identifier, 'status': 'finished', 'exit_code': result.exit_code,
                'output': result.output, 'truncated': result.truncated}

    async def interrupt(self, identifier):
        task, path = self.jobs[identifier]
        if task.done():
            return self.poll(identifier)
        group = None
        for _ in range(10):
            response = await self.backend.environment.exec('cat ' + shlex.quote(path), timeout_sec=5)
            if response.return_code == 0:
                raw = (response.stdout or '').strip()
                if not raw.isdecimal() or int(raw) <= 1:
                    raise RuntimeError('Invalid container process-group record')
                group = int(raw)
                break
            if task.done():
                return self.poll(identifier)
            await asyncio.sleep(.05)
        if group is None:
            raise RuntimeError('Command has not published its container process group')
        # There is deliberately no host os.kill/subprocess call here. The task
        # may modify its own record, so this is not an adversarial intra-task
        # security boundary. The whole container remains the isolation unit.
        await self.backend.environment.exec(f'kill -TERM -- -{group}', timeout_sec=5)
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=2.5)
        except TimeoutError:
            await self.backend.environment.exec(f'kill -KILL -- -{group}', timeout_sec=5)
            await asyncio.wait_for(asyncio.shield(task), timeout=5)
        return self.poll(identifier)

    async def close(self):
        failures = []
        for identifier, (task, _) in self.jobs.items():
            try:
                if not task.done():
                    await self.interrupt(identifier)
                else:
                    task.result()
            except Exception as exc:
                failures.append(type(exc).__name__)
        if failures:
            raise RuntimeError('Command cleanup failed; trial container must be destroyed: ' + ','.join(failures))
