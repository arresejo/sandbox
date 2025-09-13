import asyncio
import os
import shlex
from dataclasses import dataclass
from typing import Optional, Dict, Tuple

DEFAULT_MAX_BYTES = 200_000

class CommandError(Exception):
    """Raised for command validation / execution issues not directly from the process exit code."""

@dataclass
class ExecResult:
    code: int
    stdout: str
    stderr: str
    truncated: bool
    timeout: bool

async def run_subprocess(
    command: str,
    *,
    stdin: str = "",
    workdir: Optional[str] = None,
    timeout: Optional[float] = None,
    shell: bool = True,
    env: Optional[Dict[str, str]] = None,
    encoding: str = "utf-8",
    max_output_bytes: int = DEFAULT_MAX_BYTES,
) -> ExecResult:
    """Execute a command robustly.

    Returns ExecResult. Raises CommandError for validation or timeout.
    """
    if not command or not command.strip():
        raise CommandError("Empty command")

    if workdir:
        if not os.path.isdir(workdir):
            raise CommandError(f"Invalid workdir: {workdir}")

    env_combined = os.environ.copy()
    if env:
        env_combined.update(env)

    # Choose shell vs exec (shell true allows pipes, redirection)
    if shell:
        create = asyncio.create_subprocess_shell(
            command,
            stdin=asyncio.subprocess.PIPE if stdin else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=workdir,
            env=env_combined,
        )
    else:
        parts = shlex.split(command)
        if not parts:
            raise CommandError("Command parsing produced empty argv")
        create = asyncio.create_subprocess_exec(
            *parts,
            stdin=asyncio.subprocess.PIPE if stdin else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=workdir,
            env=env_combined,
        )

    proc = await create

    send_input = stdin.encode(encoding) if stdin else None
    try:
        stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(send_input), timeout=timeout)
        timed_out = False
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        raise CommandError(f"Timeout after {timeout}s")

    stdout_b = stdout_b or b""
    stderr_b = stderr_b or b""

    truncated = False
    if len(stdout_b) > max_output_bytes:
        stdout_b = stdout_b[:max_output_bytes] + b"\n...[TRUNCATED]..."
        truncated = True
    if len(stderr_b) > max_output_bytes:
        stderr_b = stderr_b[:max_output_bytes] + b"\n...[TRUNCATED]..."
        truncated = True

    stdout = stdout_b.decode(encoding, errors="replace")
    stderr = stderr_b.decode(encoding, errors="replace")

    return ExecResult(code=proc.returncode, stdout=stdout, stderr=stderr, truncated=truncated, timeout=timed_out)
