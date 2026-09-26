"""Container-side output capture for the next custom runtime.

The helper is sent through Harbor, never used to execute agent commands on the
host. A background child retaining stdout must not keep a finished shell open.
"""
import inspect
import math


def capture(command, seconds, max_bytes):
    import os
    import selectors
    import signal
    import subprocess
    import time

    process = subprocess.Popen(['bash', '-c', command], stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, start_new_session=True)
    selector = selectors.DefaultSelector()
    os.set_blocking(process.stdout.fileno(), False)
    selector.register(process.stdout, selectors.EVENT_READ)
    deadline = time.monotonic() + seconds
    finished_at = None
    timed_out = False
    pipe_open = True
    kept = bytearray()
    truncated = False

    def terminate(sig):
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            pass

    try:
        while True:
            now = time.monotonic()
            if process.poll() is None and now >= deadline and not timed_out:
                timed_out = True
                terminate(signal.SIGTERM)
            if timed_out and now >= deadline + 2:
                terminate(signal.SIGKILL)
            if process.poll() is not None:
                if finished_at is None:
                    finished_at = now
                if not pipe_open:
                    break
                # Drain queued output briefly; do not wait for a daemon to
                # close its inherited descriptor. Services remain available.
                if now - finished_at >= .15:
                    truncated = True
                    break
            if now >= deadline + 4:
                terminate(signal.SIGKILL)
                process.wait(timeout=1)
                truncated = pipe_open or truncated
                break
            events = selector.select(.025) if pipe_open else []
            if not pipe_open:
                time.sleep(.025)
            for key, _ in events:
                try:
                    data = os.read(key.fd, 8192)
                except BlockingIOError:
                    continue
                if not data:
                    selector.unregister(process.stdout)
                    pipe_open = False
                    continue
                remaining = max_bytes - len(kept)
                kept.extend(data[:remaining])
                truncated = truncated or len(data) > remaining
        code = process.wait(timeout=1)
        return dict(output=kept.decode('utf-8', errors='replace'),
            exit_code=124 if timed_out else code if code >= 0 else 128 - code,
            truncated=truncated)
    except BaseException:
        terminate(signal.SIGKILL)
        process.wait(timeout=1)
        raise
    finally:
        selector.close()
        process.stdout.close()


def capture_script(command, seconds, max_bytes):
    if not isinstance(command, str) or '\x00' in command:
        raise ValueError('Invalid container command')
    if (type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds <= 0
            or type(max_bytes) is not int or max_bytes <= 0):
        raise ValueError('Positive capture limits required')
    return (inspect.getsource(capture) + '\nimport json\nprint(json.dumps(capture('
        + repr(command) + ', ' + repr(seconds) + ', ' + repr(max_bytes) + ')))\n')
