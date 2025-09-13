import asyncio
import os
from typing import Optional
from fastmcp import FastMCP
from command_exec import run_subprocess, CommandError

mcp = FastMCP("Server")


@mcp.tool(
    title="Spawn sandbox",
    description="Create (if absent) and keep a named sandbox container running (detached). Returns container id.",
)
async def spawn_sandbox() -> dict:
    command = "docker run -d --name sandbox sandbox-image tail -f /dev/null"

    process = await asyncio.create_subprocess_shell(
        command,
        # stdin=asyncio.subprocess.PIPE if stdin else None,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        text=False,
    )
    # Envoyer l'input si fourni
    # stdout, stderr = await process.communicate(input=stdin)
    stdout, stderr = await process.communicate()

    return {
        "stdout": stdout,
        "stderr": stderr,
        "return_code": process.returncode,
        "command": command,
    }


@mcp.tool(
    title="List file",
    description="List the files in the sandbox",
)
async def list_files() -> dict:
    command = "docker run -d --name sandbox sandbox-image tail -f /dev/null"

    process = await asyncio.create_subprocess_shell(
        command,
        # stdin=asyncio.subprocess.PIPE if stdin else None,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        text=False,
    )
    # Envoyer l'input si fourni
    # stdout, stderr = await process.communicate(input=stdin)
    stdout, stderr = await process.communicate()

    return {
        "stdout": stdout,
        "stderr": stderr,
        "return_code": process.returncode,
        "command": command,
    }


@mcp.tool(
    name="run_command",
    title="Run Command",
    description="Execute a system command. Supports stdin, working directory, timeout and output truncation.",
)
async def run_command(
    command: str,
    stdin: str = "",
    workdir: Optional[str] = None,
    timeout: Optional[float] = None,
    shell: bool = True,
    max_output_bytes: int = 200_000,
) -> dict:
    """Execute a command and return structured segments.

    Returns a dict with segments list: each segment has name and text.
    Errors return is_error True and may omit stdout if not produced.
    """
    try:
        result = await run_subprocess(
            command,
            stdin=stdin,
            workdir=workdir,
            timeout=timeout,
            shell=shell,
            max_output_bytes=max_output_bytes,
        )
    except CommandError as ce:
        return {
            "is_error": True,
            "message": str(ce),
            "command": command,
        }
    segments = []
    if result.stdout:
        segments.append({"name": "STDOUT", "text": result.stdout})
    if result.stderr:
        segments.append({"name": "STDERR", "text": result.stderr})
    meta = {
        "exit_code": result.code,
        "truncated": result.truncated,
        "timeout": result.timeout,
        "command": command,
    }
    is_error = result.code != 0
    if is_error:
        meta["is_error"] = True
    return {"segments": segments, **meta}


@mcp.prompt
def command_help() -> str:
    return (
        "Run shell commands. Parameters: command (required), stdin (optional string), workdir (path), timeout (seconds), shell (bool), max_output_bytes (int). "
        "Returns segments STDOUT/STDERR; sets is_error when exit_code != 0. Output may be truncated with marker."
    )


if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        port=3000,
        stateless_http=True,
        log_level="DEBUG",  # change this if this is too verbose
    )
