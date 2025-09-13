from command_exec import run_subprocess, CommandError


async def ensure_sandbox_exists():
    """
    Check if a container named sandbox already exists.
    If not, create it with ports exposed.
    """

    print("check if sandbox exists")
    check_command = "docker ps -a --format '{{.Names}}' | grep -w sandbox"

    check_result = await run_subprocess(
        check_command,
        shell=True,
    )

    if check_result.code != 0:
        print("create sandbox")
        command = (
            "docker run -d --name sandbox "
            "-p 8080:8080 -p 4041:4040 "
            "sandbox-image tail -f /dev/null"
        )
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