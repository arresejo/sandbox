import asyncio
import subprocess
import json
from fastmcp import FastMCP

mcp = FastMCP("Server", port=3000, stateless_http=True, debug=True)


@mcp.tool(
    title="Spawn sandbox",
    description="Creates a sandbox (a docker container) in which can execute commands",
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
    title="Command Executor",
    description="Execute a system command with optional stdin and return stdout, stderr, and exit code.",
)
async def run_command(command: str, stdin: str = None) -> dict:
    """
    Execute a system command and return the output.

    Args:
        command: The command to execute (e.g., 'ls -la', 'echo hello')
        stdin: Optional input to pass to the command

    Returns:
        Dictionary containing stdout, stderr, and return code
    """
    try:
        # Exécuter la commande
        process = await asyncio.create_subprocess_shell(
            command,
            stdin=asyncio.subprocess.PIPE if stdin else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            text=True,
        )

        # Envoyer l'input si fourni
        stdout, stderr = await process.communicate(input=stdin)

        return {
            "stdout": stdout,
            "stderr": stderr,
            "return_code": process.returncode,
            "command": command,
        }

    except Exception as e:
        return {
            "stdout": "",
            "stderr": f"Error executing command: {str(e)}",
            "return_code": -1,
            "command": command,
        }


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


# @mcp.prompt
# def command_help() -> str:
#     """Get help for using the command execution tool"""
#     return """
#     This server provides command execution capabilities. Use the run_command tool to execute system commands.

#     Examples:
#     - List files: run_command("ls -la")
#     - Check disk space: run_command("df -h")
#     - Echo text: run_command("echo 'Hello World'")
#     - With stdin: run_command("cat", stdin="Hello from stdin")

#     ⚠️  Warning: Be careful with the commands you execute!
#     """


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
