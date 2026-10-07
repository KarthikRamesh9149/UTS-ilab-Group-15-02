"""Run the packaged harness tests without credentials or network access."""
import os
from pathlib import Path
import socket
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


def no_network(*args, **kwargs):
    raise RuntimeError("Network access is disabled during offline tests")


if __name__ == "__main__":
    for key in list(os.environ):
        if (key.startswith(("OPENAI_", "OPENROUTER_", "LANGSMITH_", "LANGCHAIN_", "LANGFUSE_"))
                or key.endswith(("_API_KEY", "_ACCESS_TOKEN"))):
            del os.environ[key]
    os.environ["LANGSMITH_TRACING"] = "false"
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    socket.create_connection = no_network
    socket.socket.connect = no_network
    socket.socket.connect_ex = no_network
    sys.path[:0] = [str(ROOT / "src"), str(ROOT)]
    suite = unittest.TestSuite([
        unittest.defaultTestLoader.discover(str(ROOT / "tests/results"),
                                            pattern="test_*.py", top_level_dir=str(ROOT)),
        unittest.defaultTestLoader.discover(str(ROOT / "tests/harness"),
                                            pattern="test_*.py", top_level_dir=str(ROOT)),
    ])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
