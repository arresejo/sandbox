from typing import Optional
from fastmcp import FastMCP
from command_exec import run_subprocess, CommandError
from datetime import datetime
from utils.init_sandbox import ensure_sandbox_exists
from shlex import quote
import os

from fastmcp.server.dependencies import get_http_headers

# Load environment variables from .env if present
from dotenv import load_dotenv

load_dotenv()

# Use base64 to avoid shell escaping issues
import base64


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

## get_workspace_public_url
Description: Start http.server + ngrok inside the sandbox container and return the public URL. This tool allow you to expose the /workspace directory over the internet for easy file access and serving.

Parameters:

- `port` (optional, int): port of the server to expose publicly

Return shape:
- `url`: the public URL if successful.
- `is_error` / `message`: present on failure.
""",
)


@mcp.tool(
    name="get_workspace_public_url",
    title="Get Workspace Public URL",
    description="Start http.server + ngrok inside the sandbox container and return the public URL. This tool allow you to expose the /workspace directory over the internet for easy file access and serving.",
)
async def get_workspace_public_url(port: int = 8000) -> dict:
    print("port", port)
    await ensure_sandbox_exists()

    # start http.server (serves /workspace)
    await run_subprocess(
        "docker exec -d sandbox python -m http.server 8000", shell=True
    )

    # start ngrok using auth token from environment
    ngrok_token = os.getenv("NGROK_AUTHTOKEN")
    if not ngrok_token:
        return {"is_error": True, "message": "Missing NGROK_AUTHTOKEN in environment"}

    await run_subprocess(
        f"docker exec -d sandbox ngrok http {port} --authtoken {ngrok_token} --log=stdout",
        shell=True,
    )

    # fetch public URL via ngrok's local API *inside* the container
    cmd = "docker exec sandbox sh -c 'curl -s http://127.0.0.1:4040/api/tunnels | jq -r \".tunnels[0].public_url\"'"
    result = await run_subprocess(cmd, shell=True)

    if (
        result.code == 0
        and result.stdout
        and result.stdout.strip()
        and result.stdout.strip() != "null"
    ):
        url = result.stdout.strip()
        return {"is_error": False, "url": url}

    return {"is_error": True, "message": result.stderr or "No public URL found"}


@mcp.tool(
    title="List files in the sandbox",
    description="List the files in the sandbox workspace directory",
)
async def list_files() -> dict:
    await ensure_sandbox_exists()

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
    await ensure_sandbox_exists()

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


@mcp.tool(
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
    await ensure_sandbox_exists()

    # Normalize potential accidental code fences
    if content.startswith("```") and content.endswith("```"):
        lines = content.splitlines()
        if len(lines) >= 2:
            inner = lines[1:-1]
            content = "\n".join(inner) + ("\n" if content.endswith("\n```") else "")

    # Write the file inside the sandbox container
    # Use /workspace as the root inside the container

    # If path is absolute, use as is; if relative, prepend /workspace
    container_path = path
    if not os.path.isabs(container_path):
        container_path = f"/workspace/{container_path}"
    # Ensure parent directories exist inside the container
    mkdir_cmd = f"mkdir -p $(dirname {quote(container_path)})"
    # Write content using echo and redirection (handle special chars with printf)

    encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
    write_cmd = f"echo '{encoded}' | base64 -d > {quote(container_path)}"
    full_cmd = f"{mkdir_cmd} && {write_cmd}"
    docker_cmd = f"docker exec sandbox sh -c {quote(full_cmd)}"

    try:
        result = await run_subprocess(docker_cmd, shell=True)
        if result.code != 0:
            return {
                "is_error": True,
                "message": result.stderr or "Unknown error",
                "path": path,
            }
        # Get file size inside container
        stat_cmd = f"docker exec sandbox sh -c 'stat -c %s {quote(container_path)}'"
        stat_result = await run_subprocess(stat_cmd, shell=True)
        if stat_result.code == 0 and stat_result.stdout:
            bytes_written = int(stat_result.stdout.strip())
        else:
            bytes_written = len(content.encode("utf-8"))
        return {
            "path": container_path,
            "bytes_written": bytes_written,
            "created": True,  # always True for this context
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    except Exception as e:
        return {
            "is_error": True,
            "message": f"Failed to write file in sandbox: {e}",
            "path": path,
        }


@mcp.tool(
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
    await ensure_sandbox_exists()

    container_path = path
    if not os.path.isabs(container_path):
        container_path = f"/workspace/{container_path}"

    # Check if file exists in container
    check_cmd = f"docker exec sandbox sh -c 'test -f {quote(container_path)}'"
    check_result = await run_subprocess(check_cmd, shell=True)
    if check_result.code != 0:
        return {"is_error": True, "message": "File does not exist", "path": path}

    # Read file content from container (base64 to avoid encoding issues)
    read_cmd = f"docker exec sandbox sh -c 'base64 {quote(container_path)}'"
    read_result = await run_subprocess(read_cmd, shell=True)
    if read_result.code != 0 or not read_result.stdout:
        return {
            "is_error": True,
            "message": f"Failed to read file: {read_result.stderr or 'Unknown error'}",
            "path": path,
        }
    try:
        original = base64.b64decode(read_result.stdout.encode("utf-8")).decode("utf-8")
    except Exception as e:
        return {
            "is_error": True,
            "message": f"Failed to decode file: {e}",
            "path": path,
        }

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

    changed = modified != original
    if changed:
        # Write back to file in container using base64
        encoded = base64.b64encode(modified.encode("utf-8")).decode("ascii")
        write_cmd = f"echo '{encoded}' | base64 -d > {quote(container_path)}"
        docker_cmd = f"docker exec sandbox sh -c {quote(write_cmd)}"
        write_result = await run_subprocess(docker_cmd, shell=True)
        if write_result.code != 0:
            return {
                "is_error": True,
                "message": f"Failed to write file: {write_result.stderr or 'Unknown error'}",
                "path": path,
            }

    return {
        "path": container_path,
        "changed": changed,
        "replacements": applied,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


# @mcp.tool(
#     title="Push Files to GitHub",
#     description="Push files in the sandbox to Github, creating a new repository first.",
# )
# async def push_files(repo_name: str = "default_name") -> dict:
#     await ensure_sandbox_exists()

#     # 1. Get repo name (use timestamp for uniqueness)
#     repo_name = f"sandbox-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
#     org = None  # Optionally set to a GitHub org
#     full_repo = repo_name if not org else f"{org}/{repo_name}"

#     # 2. Get GH token from special header (injected by infra)
#     headers = get_http_headers()
#     print("headers", headers)
#     gh_token = headers.get("gh-api-token").split(" ")[1]
#     print("gh-api-key", gh_token)

#     if not gh_token:
#         return {
#             "is_error": True,
#             "message": "Missing GitHub API key in environment (GH_API_KEY or gh-api-key)",
#         }

#     # 4. All commands run inside the sandbox container, in /workspace
#     cmds = []
#     # a. Init git if needed
#     cmds.append("git init -b main")
#     cmds.append("git config user.email 'sandbox@example.com'")
#     cmds.append("git config user.name 'sandbox-bot'")
#     # b. Add all files
#     cmds.append("git add .")
#     cmds.append("git commit -m 'Initial commit'")
#     # c. Create repo with gh CLI
#     cmds.append(
#         f"gh repo create {full_repo} --public --source=. --remote=origin --push --confirm"
#     )

#     # d. If gh CLI fails to push, try manual push
#     cmds.append("git push origin main")

#     # 5. Run each command, collect output
#     results = []
#     for cmd in cmds:
#         docker_cmd = f"docker exec -e GH_TOKEN='{gh_token}' sandbox sh -c {quote(cmd)}"
#         try:
#             res = await run_subprocess(docker_cmd, shell=True)
#             results.append(
#                 {
#                     "command": cmd,
#                     "code": res.code,
#                     "stdout": res.stdout,
#                     "stderr": res.stderr,
#                 }
#             )
#             if res.code != 0:
#                 return {
#                     "is_error": True,
#                     "message": f"Command failed: {cmd}",
#                     "results": results,
#                 }
#         except CommandError as ce:
#             return {
#                 "is_error": True,
#                 "message": str(ce),
#                 "command": cmd,
#                 "results": results,
#             }

#     # 6. Compose repo URL
#     repo_url = f"https://github.com/{full_repo}"
#     return {"repo": full_repo, "url": repo_url, "results": results, "is_error": False}


if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        port=3000,
        stateless_http=True,
        log_level="DEBUG",  # change this if this is too verbose
    )
