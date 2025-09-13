from fastmcp import FastMCP
from command_exec import run_subprocess, CommandError
from datetime import datetime
from utils.init_sandbox import ensure_sandbox_exists
from shlex import quote
import os
from fastmcp.server.dependencies import get_http_headers

# Use base64 to avoid shell escaping issues
import base64


mcp = FastMCP("Sandbox")


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


# --- DEPLOY TOOL ---
# https://gofastmcp.com/servers/context#http-headers
@mcp.tool(
    name="deploy",
    title="Deploy Sandbox to New GitHub Repo",
    description="Creates a new GitHub repo and pushes the contents of the sandbox to it.",
)
async def deploy(
    repo_name: str, visibility: str = "private", description: str = ""
) -> dict:
    """
    Create a new GitHub repo and push the contents of the sandbox to it.
    Args:
        repo_name: Name for the new repository
        visibility: 'private' or 'public' (default: private)
        description: Optional repo description
    Returns:
        Dict with repo URL and status
    """
    print("DEPLOY CALLED")
    await ensure_sandbox_exists()

    # Get the GitHub API key from the Bearer header
    # The MCP runtime should provide this in the tool call context
    try:
        headers = get_http_headers()
        print("headers", headers)
        gh_token = headers.get("gh-api-key")
        print("gh_token", gh_token)
    except Exception as e:
        print(e)

    if not gh_token:
        return {
            "is_error": True,
            "message": "Missing GitHub API key in 'gh-api-key' header.",
        }

    # Prepare commands to run inside the container
    # 1. Set up git config and gh auth
    # 2. Create repo with gh
    # 3. Initialize git, add, commit, push
    commands = [
        # Authenticate gh CLI
        f"echo {quote(gh_token)} | gh auth login --with-token",
        # Create the repo
        f"gh repo create {quote(repo_name)} --{visibility} --description {quote(description)} --confirm",
        # Initialize git if needed
        "[ -d .git ] || git init",
        # Set default branch
        "git checkout -B main",
        # Add all files
        "git add .",
        # Commit (ignore error if nothing to commit)
        "git commit -m 'Initial commit from sandbox' || true",
        # Set remote (force overwrite)
        f"git remote remove origin 2>/dev/null || true; git remote add origin https://github.com/$(gh api user | jq -r .login)/{repo_name}.git",
        # Push
        "git push -u origin main --force",
    ]
    # Join commands with '&&' to fail fast
    full_cmd = " && ".join(commands)
    docker_cmd = f"docker exec sandbox sh -c {quote(full_cmd)}"

    try:
        result = await run_subprocess(docker_cmd, shell=True, timeout=120)
        if result.code != 0:
            return {
                "is_error": True,
                "message": result.stderr or "Failed to deploy repo.",
                "exit_code": result.code,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        # Get username for repo URL
        user_cmd = "docker exec sandbox gh api user --jq .login"
        user_result = await run_subprocess(user_cmd, shell=True)
        if user_result.code == 0 and user_result.stdout:
            username = user_result.stdout.strip()
            repo_url = f"https://github.com/{username}/{repo_name}"
        else:
            repo_url = f"https://github.com/unknown/{repo_name}"
        return {
            "repo_url": repo_url,
            "status": "success",
            "stdout": result.stdout,
        }
    except Exception as e:
        return {"is_error": True, "message": f"Exception: {e}"}


if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        port=3000,
        stateless_http=True,
        log_level="DEBUG",  # change this if this is too verbose
    )
