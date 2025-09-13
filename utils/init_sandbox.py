from command_exec import run_subprocess, CommandError


def ensure_sandbox_exists(func):
    """
    Check if a container named sandbox already exists.
    If not, create it.
    """

    async def wrapper(*args, **kwargs):

        check_command = "docker ps -a --format '{{.Names}}' | grep -w sandbox"

        check_result = await run_subprocess(
            check_command,
            shell=True,
        )

        if check_result.code != 0:
            # Container doesn't exists create it
            command = "docker run -d --name sandbox sandbox-image tail -f /dev/null"
            try:
                await run_subprocess(
                    command,
                    shell=True,
                )
            except CommandError as ce:
                return {
                    "is_error": True,
                    "message": str(ce),
                    "command": command,
                }

        func(*args, **kwargs)

    return wrapper
