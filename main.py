import asyncio
import os
from typing import Optional, List
from fastmcp import FastMCP
from command_exec import run_subprocess, CommandError
from datetime import datetime
from pathlib import Path
import mimetypes

ROOT = Path(__file__).parent.resolve()
MAX_READ_BYTES = 500_000  # ~500 KB safety cap
MAX_DIR_ENTRIES = 500

def resolve_secure_path(path: str) -> Path:
    """Resolve a user-supplied path safely within project root.

    Expands ~, resolves symlinks, and ensures final path is within ROOT.
    Raises ValueError if path escapes root.
    """
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = (ROOT / p).resolve()
    else:
        p = p.resolve()
    try:
        p.relative_to(ROOT)
    except ValueError:
        raise ValueError("Path escapes project root")
    return p

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
    name="read_file",
    title="Read File",
    description="Return full textual content of a file (with size/binary safeguards).",
)
async def read_file(path: str) -> dict:
    """Read a text file within the project root with safety checks.

    Returns content (possibly truncated) and metadata. Rejects large or binary files.
    """
    try:
        p = resolve_secure_path(path)
    except ValueError as e:
        return {"is_error": True, "message": str(e), "path": path}

    if not p.exists():
        return {"is_error": True, "message": "File does not exist", "path": str(p)}
    if p.is_dir():
        return {"is_error": True, "message": "Path is a directory", "path": str(p)}

    try:
        size = p.stat().st_size
        if size > MAX_READ_BYTES:
            return {"is_error": True, "message": f"File too large (>{MAX_READ_BYTES} bytes)", "path": str(p), "size": size}

        # rudimentary binary detection: look for null bytes in first chunk
        chunk = p.read_bytes()[:2048]
        if b"\x00" in chunk:
            return {"is_error": True, "message": "Binary file likely (null bytes detected)", "path": str(p)}

        text = p.read_text(encoding="utf-8")
        truncated = False
        if len(text.encode('utf-8')) > MAX_READ_BYTES:
            # Shouldn't happen due to earlier size check, but double-guard
            enc = text.encode('utf-8')[:MAX_READ_BYTES]
            text = enc.decode('utf-8', errors='ignore') + "\n<!-- TRUNCATED -->\n"
            truncated = True
        return {
            "path": str(p),
            "content": text,
            "truncated": truncated,
            "size": size,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    except Exception as e:
        return {"is_error": True, "message": f"Failed to read file: {e}", "path": str(p)}


@mcp.tool(
    name="list_file",
    title="List Directory",
    description="List files/directories at a path within project root (non-recursive).",
)
async def list_file(path: str = ".") -> dict:
    """Enumerate directory entries with basic metadata.

    Limits number of entries; returns a truncated flag if limit exceeded.
    """
    try:
        p = resolve_secure_path(path)
    except ValueError as e:
        return {"is_error": True, "message": str(e), "path": path}

    if not p.exists():
        return {"is_error": True, "message": "Path does not exist", "path": str(p)}
    if not p.is_dir():
        return {"is_error": True, "message": "Path is not a directory", "path": str(p)}

    entries = []
    truncated = False
    try:
        for idx, child in enumerate(sorted(p.iterdir(), key=lambda c: c.name.lower())):
            if idx >= MAX_DIR_ENTRIES:
                truncated = True
                break
            kind = "directory" if child.is_dir() else "file"
            size = None
            if child.is_file():
                try:
                    size = child.stat().st_size
                except Exception:
                    size = None
            entry = {"name": child.name + ("/" if child.is_dir() else ""), "type": kind}
            if size is not None:
                entry["size"] = size
            entries.append(entry)
        return {
            "path": str(p),
            "entries": entries,
            "truncated": truncated,
            "count": len(entries),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    except Exception as e:
        return {"is_error": True, "message": f"Failed to list directory: {e}", "path": str(p)}


@mcp.tool(
    title="Command Executor",
    description="Execute a system command with optional stdin and return stdout, stderr, and exit code.",
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


@mcp.tool(
    name="write_to_file",
    title="Write File (create/overwrite)",
    description="Create or overwrite a text file with provided full content. Creates parent directories as needed.",
)
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
            applied.append({"index": idx, "status": "skipped", "reason": "missing search"})
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
            return {"is_error": True, "message": f"Failed to write file: {e}", "path": path}

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
