"""Full local diagnostics; only explicitly curated metadata may leave this volume."""
import json
import os
from pathlib import Path
import threading
import time
from langchain_core.callbacks import BaseCallbackHandler
from local_observation import DetailObserver
from local_graph_callbacks import LocalGraphCallbacks


class PrivateLog:
    def __init__(self, path):
        self.path = path
        path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.lock = threading.Lock()

    def record(self, kind, **fields):
        with self.lock, self.path.open('a') as stream:
            stream.write(json.dumps(dict(time_ns=time.time_ns(),kind=kind,**fields),default=str)+'\n')
            stream.flush()
            os.fsync(stream.fileno())


class LoggedEnvironment:
    def __init__(self, environment, log):
        self.environment, self.log = environment, log

    def __getattr__(self, name):
        return getattr(self.environment,name)

    async def exec(self, command, **kwargs):
        started = time.time_ns()
        try:
            result = await self.environment.exec(command,**kwargs)
            self.log.record('container_exec',started_ns=started,command=command,options=kwargs,
                return_code=result.return_code,stdout=result.stdout,stderr=result.stderr)
            return result
        except BaseException as error:
            self.log.record('container_exec_error',started_ns=started,command=command,
                error_type=type(error).__name__)
            raise

    async def upload_file(self, source_path, target_path):
        self.log.record('upload_file',source=str(source_path),target=str(target_path))
        return await self.environment.upload_file(source_path=source_path,target_path=target_path)

    async def upload_dir(self, source_dir, target_dir):
        self.log.record('upload_dir',source=str(source_dir),target=str(target_dir))
        return await self.environment.upload_dir(source_dir=source_dir,target_dir=target_dir)


class ToolCallbacks(LocalGraphCallbacks):
    def __init__(self, recorder, private_log):
        super().__init__(DetailObserver(recorder))
        self.private_log = private_log
        self.tool_active = {}

    def on_tool_start(self, serialized, input_str, *, run_id, **kwargs):
        self.tool_active[run_id] = time.time_ns(),time.monotonic()
        self.private_log.record('tool_start',run_id=str(run_id),tool=serialized.get('name'),input=input_str)

    def on_tool_end(self, output, *, run_id, **kwargs):
        self.private_log.record('tool_end',run_id=str(run_id),output=output)
        started = self.tool_active.pop(run_id,None)
        if started:
            self.observer.emit('tool',*started,'ok',{'tool_calls':1})

    def on_tool_error(self, error, *, run_id, **kwargs):
        self.private_log.record('tool_error',run_id=str(run_id),error_type=type(error).__name__)
        started = self.tool_active.pop(run_id,None)
        if started:
            self.observer.emit('tool',*started,'error',{'tool_calls':1})
