from typing import Optional
from fastmcp import FastMCP
from command_exec import run_subprocess, CommandError
from datetime import datetime
from pathlib import Path
from utils.init_sandbox import ensure_sandbox_exists

mcp = FastMCP("Sandbox")


@mcp.tool(
    title="List files in the sandbox",
    description="List the files in the sandbox workspace directory",
)
@ensure_sandbox_exists
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


# @mcp.tool(
#     name="run_command",
#     title="Run Command in the Sandbox",
#     description="Execute a command inside the sandbox container. Supports stdin, timeout and output truncation.",
# )
# @ensure_sandbox_exists
# async def run_command(
#     command: str,
#     stdin: str = "",
#     timeout: Optional[float] = None,
#     shell: bool = True,
#     max_output_bytes: int = 200_000,
# ) -> dict:
#     """Execute a command inside the sandbox container and return structured segments.

#     Returns a dict with segments list: each segment has name and text.
#     Errors return is_error True and may omit stdout if not produced.
#     """
#     # Use stdin to pipe the script into the container for robust multi-line support
#     docker_command = "docker exec -i sandbox sh"

#     try:
#         # If stdin is provided, prepend the command to it; otherwise, use command as stdin
#         script = command if not stdin else f"{command}\n{stdin}"
#         result = await run_subprocess(
#             docker_command,
#             stdin=script,
#             timeout=timeout,
#             shell=shell,
#             max_output_bytes=max_output_bytes,
#         )
#     except CommandError as ce:
#         return {
#             "is_error": True,
#             "message": str(ce),
#             "command": command,
#         }
#     segments = []
#     if result.stdout:
#         segments.append({"name": "STDOUT", "text": result.stdout})
#     if result.stderr:
#         segments.append({"name": "STDERR", "text": result.stderr})
#     meta = {
#         "exit_code": result.code,
#         "truncated": result.truncated,
#         "timeout": result.timeout,
#         "command": command,
#     }
#     is_error = result.code != 0
#     if is_error:
#         meta["is_error"] = True
#     return {"segments": segments, **meta}


# @mcp.prompt
# def command_help() -> str:
#     return (
#         "Run shell commands inside the sandbox container. Parameters: command (required), stdin (optional string), timeout (seconds), shell (bool), max_output_bytes (int). "
#         "Returns segments STDOUT/STDERR; sets is_error when exit_code != 0. Output may be truncated with marker."
#     )


@mcp.tool(
    name="write_to_file",
    title="Write File (create/overwrite)",
    description="Create or overwrite a text file with provided full content. Creates parent directories as needed.",
)
@ensure_sandbox_exists
async def write_to_file(path: str, content: str) -> dict:
    """Create or overwrite a file atomically-ish.

    Args:
        path: Target file path (relative or absolute)
        content: Entire desired file content
    Returns:
        Metadata including bytes_written and absolute path
    Args Example:
        path="~/output.txt",
        content="Full file content here"
    """
    try:
        p = Path(path).expanduser().resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        # Normalize potential accidental code fences
        if content.startswith("```") and content.endswith("```"):
            # remove first and last fence line
            lines = content.splitlines()
            if len(lines) >= 2:
                # drop first and last
                inner = lines[1:-1]
                content = "\n".join(inner) + ("\n" if content.endswith("\n```") else "")
        data = content
        p.write_text(data, encoding="utf-8")
        return {
            "path": str(p),
            "bytes_written": len(data.encode("utf-8")),
            "created": not p.exists(),  # always False after write; placeholder kept for schema similarity
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    except Exception as e:
        return {"is_error": True, "message": f"Failed to write file: {e}", "path": path}


@mcp.tool(
    name="replace_in_file",
    title="Replace In File",
    description="Apply multiple search/replace edits to an existing text file. Each replacement is literal (no regex).",
)
@ensure_sandbox_exists
async def replace_in_file(path: str, replacements: list[dict]) -> dict:
    """Perform targeted replacements.

    Args:
        path: File to modify
        replacements: list of {"search": str, "replace": str}
    Returns metadata with counts.
    Args Example:
        replacements=[
            {"search": "old_text", "replace": "new_text"},
            {"search": "another_old", "replace": "another_new"},
        ]
    """
    p = Path(path).expanduser()
    if not p.exists():
        return {"is_error": True, "message": "File does not exist", "path": path}
    try:
        original = p.read_text(encoding="utf-8")
    except Exception as e:
        return {"is_error": True, "message": f"Failed to read file: {e}", "path": path}

    modified = original
    applied = []
    for idx, entry in enumerate(replacements):
        search = entry.get("search")
        replace = entry.get("replace", "")
        if search is None:
            applied.append(
                {"index": idx, "status": "skipped", "reason": "missing search"}
            )
            continue
        if search not in modified:
            applied.append({"index": idx, "status": "not-found"})
            continue
        occurrences = modified.count(search)
        modified = modified.replace(search, replace)
        applied.append({"index": idx, "status": "replaced", "occurrences": occurrences})

    if modified != original:
        try:
            p.write_text(modified, encoding="utf-8")
        except Exception as e:
            return {
                "is_error": True,
                "message": f"Failed to write file: {e}",
                "path": path,
            }

    return {
        "path": str(p.resolve()),
        "changed": modified != original,
        "replacements": applied,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        port=3000,
        stateless_http=True,
        log_level="DEBUG",  # change this if this is too verbose
    )
