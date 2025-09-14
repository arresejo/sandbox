from typing import Optional
from fastmcp import FastMCP
from datetime import datetime
from pathlib import Path
import os, base64, httpx

# Base URL of sandbox API service (must be reachable inside Railway project network)
SANDBOX_BASE_URL = os.environ.get("SANDBOX_BASE_URL", "sandbox-production-87b4.up.railway.app:3000")
PORT = int(os.environ.get("PORT", "3000"))

mcp = FastMCP(
    name="Sandbox MCP",
    instructions="""
TOOL USE

You have access to a set of tools that are executed upon the user's approval. You will receive the result of that tool use. You use tools step-by-step to accomplish a given task, with each tool use informed by the result of the previous tool use.

## write_to_file

Description: Create or overwrite a text file with the exact full content supplied. Parent directories are created as needed. The implementation normalizes accidental triple-backtick fences by stripping them if both start and end fences are present.

Parameters (match `main.py` implementation):

- `path` (required, string): Target file path (relative or absolute). Home `~` is expanded.
- `content` (required, string): Full desired file content. Provide the entire file body.

Return shape:

- `path`: absolute resolved path that was written.
- `bytes_written`: number of bytes written.
- `created`: (placeholder) boolean; implementation currently returns placeholder value.
- `timestamp`: ISO8601 UTC timestamp of write.
- `is_error` / `message`: present on failure.

Usage example (tool call):
<write_to_file>
<path>docs/NOTE.md</path>
<content>
Project notes and documentation.
Line 2 of the file.
</content>
</write_to_file>

## replace_in_file

Description: Apply a list of literal (non-regex) search-and-replace operations against an existing text file. Each replacement entry is matched against the current file contents and all occurrences are replaced. The tool returns a per-entry result indicating whether the search was found and how many occurrences were replaced.

Parameters (match `main.py` implementation):

- `path` (required, string): Path to the file to edit (home `~` expanded).
- `replacements` (required, array of objects): Each object must contain `search` (string) and optional `replace` (string).

Return shape:

- `path`: absolute resolved file path.
- `changed`: boolean whether file content changed.
- `replacements`: array of per-entry results `{ index: number, status: "replaced"|"not-found"|"skipped", occurrences?: number, reason?: string }`.
- `timestamp`: ISO8601 UTC timestamp.
- `is_error` / `message`: present on failure.

Usage example (tool call payload):
<replace_in_file>
<path>src/utils/helper.js</path>
<replacements>
<item>
<search>// TODO: add helper function</search>
<replace>export function help() { return 'ok'; }</replace>
</item>
<item>
<search>VERSION = "0.1.0"</search>
<replace>VERSION = "0.2.0"</replace>
</item>
</replacements>
</replace_in_file>

## read_file

Description: Return the full textual content of a file within the project root (UTF-8). Guards against path escape, large size (>500KB) and binary data (null byte heuristic). Returns content plus size and timestamp.

Parameters:

- `path` (string, required): File path (relative to root or absolute). `~` expanded. Must resolve inside project root.

Return shape:

- `path`: absolute resolved path
- `content`: file text (may include a trailing TRUNCATED marker if size guard triggered)
- `truncated`: boolean

## list_file

Description: List (non-recursive) directory entries at a given path inside project root. Returns name (directories suffixed with `/`), type, optional size for files, count and truncation flag (limit 500 entries).

Parameters:

- `path` (string, optional, default "."): Directory path to enumerate.

Return shape:

- `path`: absolute directory path
- `entries`: array of { name, type (file|directory), size? }
- `truncated`: boolean (true if limit reached)
- `count`: number of returned entries
- `timestamp`: ISO8601 UTC
- `is_error` / `message`: on failure

Example tool call:
<list_file>
<path>src/</path>
</list_file>

Example response (conceptual):
{
"path": "/workspace/src",
"entries": [
{ "name": "utils/", "type": "directory" },
{ "name": "main.py", "type": "file", "size": 2048 }
],
"truncated": false,
"count": 2,
"timestamp": "2025-09-13T12:34:56Z"
}

## push_files

Description: Create a new GitHub repository and push files in the sandbox to it.

Parameters:

- `repo_name` (optional, string): Name of the GitHub repository.

Usage example (tool call):
<push_files>
<repo_name>my-sandbox-repo</repo_name>
</push_files>

Return shape:

- `repo_url`: URL of the created repository.
- `status`: "success" on success.
- `stdout`: Output from the deployment process.
- `is_error` / `message` / `stderr` / `exit_code`: present on failure.

""",
)

# ---------- helpers ----------
async def _get(path: str, params: dict | None = None):
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{SANDBOX_BASE_URL}{path}", params=params, timeout=60)
        r.raise_for_status()
        return r.json()

async def _post(path: str, json: dict):
    async with httpx.AsyncClient() as client:
        r = await client.post(f"{SANDBOX_BASE_URL}{path}", json=json, timeout=120)
        r.raise_for_status()
        return r.json()

# ---------- tools ----------
@mcp.tool(
    name="get_workspace_public_url",
    title="Get Workspace Public URL",
    description="Return the sandbox service URL (internal/private).",
)
async def get_workspace_public_url() -> dict:
    return {"is_error": False, "url": SANDBOX_BASE_URL}


@mcp.tool(
    title="List files in the sandbox",
    description="List the files in the sandbox workspace directory",
)
async def list_files() -> dict:
    data = await _get("/list")
    listing = "\n".join(
        f"{e['type']:9} {'' if e.get('size') is None else str(e['size']).rjust(8)} {e['name']}"
        for e in data.get("entries", [])
    )
    return {
        "segments": [{"name": "STDOUT", "text": listing}],
        "exit_code": 0,
        "truncated": False,
        "timeout": False,
        "command": "remote:list",
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
    res = await _post("/run", {"command": command, "stdin": stdin})
    segments = []
    if res.get("stdout"):
        out = res["stdout"]
        if len(out.encode()) > max_output_bytes:
            out = out.encode()[:max_output_bytes].decode(errors="ignore") + "\n[TRUNCATED]"
        segments.append({"name": "STDOUT", "text": out})
    if res.get("stderr"):
        err = res["stderr"]
        if len(err.encode()) > max_output_bytes:
            err = err.encode()[:max_output_bytes].decode(errors="ignore") + "\n[TRUNCATED]"
        segments.append({"name": "STDERR", "text": err})
    meta = {
        "exit_code": res.get("exit_code", 1),
        "truncated": any("[TRUNCATED]" in s["text"] for s in segments),
        "timeout": False,
        "command": command,
    }
    if meta["exit_code"] != 0:
        meta["is_error"] = True
    return {"segments": segments, **meta}


@mcp.tool(
    title="Write File (create/overwrite)",
    description="Create or overwrite a text file with provided full content. Creates parent directories as needed.",
)
async def write_to_file(path: Path, content: str) -> dict:
    if content.startswith("```") and content.endswith("```"):
        lines = content.splitlines()
        if len(lines) >= 2:
            inner = lines[1:-1]
            content = "\n".join(inner) + ("\n" if content.endswith("\n```") else "")

    b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")
    info = await _post("/write", {"path": str(path), "content_b64": b64})
    if info.get("is_error"):
        return {"is_error": True, "message": info.get("message", "Unknown error"), "path": str(path)}
    return {
        "path": info.get("path", str(path)),
        "bytes_written": info.get("bytes_written", len(content.encode("utf-8"))),
        "created": info.get("created", True),
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


@mcp.tool(
    title="Replace In File",
    description="Apply multiple search/replace edits to an existing text file. Each replacement is literal (no regex).",
)
async def replace_in_file(path: Path, replacements: list[dict]) -> dict:
    info = await _post("/replace", {"path": str(path), "replacements": replacements})
    if info.get("is_error"):
        return {"is_error": True, "message": info.get("message", "Unknown error"), "path": str(path)}
    return {
        "path": info["path"],
        "changed": info["changed"],
        "replacements": info["replacements"],
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


@mcp.tool(
    name="read_file",
    title="Read File",
    description="Return the full textual content of a sandbox file",
)
async def read_file(path: Path) -> dict:
    info = await _get("/read", params={"path": str(path)})
    if info.get("is_error"):
        return {"is_error": True, "message": info.get("message", "Unknown error"), "path": str(path)}
    return {
        "path": info["path"],
        "content": info["content"],
        "truncated": info.get("truncated", False),
    }


@mcp.tool(
    title="Push Files to GitHub",
    description="Push files in the sandbox to Github, creating a new repository first.",
)
async def push_files(repo_name: str = "default_name") -> dict:
    repo_name = repo_name or f"sandbox-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    cmds = [
        "git init -b main",
        "git config user.email 'sandbox@example.com'",
        "git config user.name 'sandbox-bot'",
        "git add .",
        "git commit -m 'Initial commit' || echo 'nothing to commit' >&2",
        f"gh repo create {repo_name} --public --source=. --remote=origin --push --confirm || true",
        "git push -u origin main || true",
    ]
    results = []
    for cmd in cmds:
        res = await _post("/run", {"command": cmd, "stdin": ""})
        results.append({
            "command": cmd,
            "code": res.get("exit_code", 1),
            "stdout": res.get("stdout", ""),
            "stderr": res.get("stderr", ""),
        })

    return {
        "repo": repo_name,
        "url": f"https://github.com/{repo_name}",
        "results": results,
        "is_error": any(r["code"] != 0 for r in results[-2:]),
    }

# ---------- entrypoint ----------
if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        port=PORT,
        stateless_http=True,
        log_level="DEBUG",
    )