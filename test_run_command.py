import asyncio
from command_exec import run_subprocess, CommandError
import os

async def test_success():
    res = await run_subprocess("echo hello")
    assert res.code == 0
    assert "hello" in res.stdout

async def test_stdin():
    res = await run_subprocess("cat", stdin="input line")
    assert res.stdout.strip() == "input line"

async def test_workdir():
    tmp = os.getcwd()
    res = await run_subprocess("pwd", workdir=tmp)
    assert tmp in res.stdout.strip()

async def test_timeout():
    try:
        await run_subprocess("sleep 2", timeout=0.5)
    except CommandError as e:
        assert "Timeout" in str(e)
    else:
        raise AssertionError("Expected timeout")

async def main():
    await test_success()
    await test_stdin()
    await test_workdir()
    await test_timeout()
    print("All tests passed")

if __name__ == "__main__":
    asyncio.run(main())
