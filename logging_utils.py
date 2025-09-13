import os
import sys
import json
from datetime import datetime

_VERBOSE = os.getenv("MCP_VERBOSE", "0") in ("1", "true", "yes", "on")


def set_verbose(v: bool):
    global _VERBOSE
    _VERBOSE = v


def _emit(level: str, message: str, data=None):
    # STDERR logging so it won't interfere with MCP STDOUT protocol messages
    ts = datetime.utcnow().isoformat() + "Z"
    if data is not None:
        line = f"[{ts}] {level} {message}: {json.dumps(data, ensure_ascii=False)}"
    else:
        line = f"[{ts}] {level} {message}"
    print(line, file=sys.stderr, flush=True)


def log_info(message: str, data=None):
    if _VERBOSE:
        _emit("INFO", message, data)


def log_warn(message: str, data=None):
    _emit("WARN", message, data)


def log_error(message: str, data=None):
    _emit("ERROR", message, data)
