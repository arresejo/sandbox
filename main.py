from typing import Optional
from fastmcp import FastMCP
from command_exec import run_subprocess, CommandError

mcp = FastMCP("Sandbox")


@mcp.tool(
    title="Spawn a sandbox",
    description="Create sandbox container, only if it's not already running. If it's already running then it's ok, does nothing. This sandbox is meant to receive and run the commands.",
)
async def spawn_sandbox() -> dict:
    command = "docker run -d --name sandbox sandbox-image tail -f /dev/null"

    try:
        result = await run_subprocess(
            command,
            shell=True,
        )
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
            "container_id": result.stdout.strip() if result.stdout else None,
        }
        is_error = result.code != 0
        if is_error:
            meta["is_error"] = True
        return {"segments": segments, **meta}
    except CommandError as ce:
        return {
            "is_error": True,
            "message": str(ce),
            "command": command,
        }


@mcp.tool(
    title="List files in the sandbox",
    description="List the files in the sandbox workspace directory",
)
async def list_files() -> dict:
    command = "docker exec sandbox ls /workspace -la"

    try:
        result = await run_subprocess(
            command,
            shell=True,
        )
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
    except CommandError as ce:
        return {
            "is_error": True,
            "message": str(ce),
            "command": command,
        }


@mcp.tool(
    name="run_command",
    title="Run Command in the Sandbox",
    description="Execute a command inside the sandbox container. Supports stdin, timeout and output truncation.",
)
async def run_command(
    command: str,
    stdin: str = "",
    timeout: Optional[float] = None,
    shell: bool = True,
    max_output_bytes: int = 200_000,
) -> dict:
    """Execute a command inside the sandbox container and return structured segments.

    Returns a dict with segments list: each segment has name and text.
    Errors return is_error True and may omit stdout if not produced.
    """
    # Use stdin to pipe the script into the container for robust multi-line support
    docker_command = "docker exec -i sandbox sh"

    try:
        # If stdin is provided, prepend the command to it; otherwise, use command as stdin
        script = command if not stdin else f"{command}\n{stdin}"
        result = await run_subprocess(
            docker_command,
            stdin=script,
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


# @mcp.prompt
# def command_help() -> str:
#     return (
#         "Run shell commands inside the sandbox container. Parameters: command (required), stdin (optional string), timeout (seconds), shell (bool), max_output_bytes (int). "
#         "Returns segments STDOUT/STDERR; sets is_error when exit_code != 0. Output may be truncated with marker."
#     )


if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        port=3000,
        stateless_http=True,
        log_level="DEBUG",  # change this if this is too verbose
    )
