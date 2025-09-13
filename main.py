import asyncio
import os
from typing import Optional
from fastmcp import FastMCP

from command_exec import run_subprocess, CommandError

mcp = FastMCP("Server", port=3000, stateless_http=True, debug=True)


@mcp.tool(
    title="Spawn sandbox",
    description="Create (if absent) and keep a named sandbox container running (detached). Returns container id.",
)
async def spawn_sandbox(name: str = "sandbox", image: str = "sandbox-image", recreate: bool = False) -> dict:
    """Ensure a long-lived detached container exists.

    Args:
        name: Container name
        image: Docker image to use
        recreate: If True and container exists, remove then recreate
    """
    async def run(cmd: str):
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await proc.communicate()
        return proc.returncode, (out or b"").decode(), (err or b"").decode()

    # Check if exists
    code, out, err = await run(f"docker ps -a --filter name=^{name}$ --format '{{{{.ID}}}} {{{{.Status}}}}'")
    if code != 0:
        return {"error": True, "message": "Failed to query docker", "stderr": err.strip(), "return_code": code}

    exists = bool(out.strip())
    if exists and recreate:
        rc, _o, e = await run(f"docker rm -f {name}")
        if rc != 0:
            return {"error": True, "message": "Failed to remove existing container", "stderr": e.strip(), "return_code": rc}
        exists = False

    if not exists:
        create_cmd = f"docker run -d --name {name} {image} tail -f /dev/null"
        rc, o, e = await run(create_cmd)
        if rc != 0:
            return {"error": True, "message": "Failed to create container", "stderr": e.strip(), "return_code": rc, "command": create_cmd}
        container_id = o.strip()
        created = True
    else:
        # If exists but maybe exited, start it
        rc, o2, e2 = await run(f"docker start {name}")
        if rc != 0:
            return {"error": True, "message": "Failed to start existing container", "stderr": e2.strip(), "return_code": rc}
        container_id = o2.strip()
        created = False

    return {"error": False, "container_id": container_id, "created": created, "name": name, "image": image}


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


# @mcp.resource("system://info")
# def get_system_info():
#     """Get basic system information"""
#     import platform
#     import os

#     return {
#         "platform": platform.platform(),
#         "python_version": platform.python_version(),
#         "working_directory": os.getcwd(),
#         "user": os.getenv("USER", "unknown"),
#     }


@mcp.prompt
def command_help() -> str:
    return (
        "Run shell commands. Parameters: command (required), stdin (optional string), workdir (path), timeout (seconds), shell (bool), max_output_bytes (int). "
        "Returns segments STDOUT/STDERR; sets is_error when exit_code != 0. Output may be truncated with marker."
    )


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
