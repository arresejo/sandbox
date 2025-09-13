## Build docker image

docker build -t sandbox-image .

## [TOOL TO IMPLEMENT] SPAWN

Spawn a container

```bash
docker run -d --name sandbox sandbox-image tail -f /dev/null
```

## Commands you can execute:

## [TOOL TO IMPLEMENT] List files in my sandbox

```bash
docker exec sandbox ls /workspace -la
```

## Create/Modify a file

```bash
docker exec sandbox sh -c 'echo "Hello World" > /workspace/myfile.txt'
```

## Get a file content

```bash
docker exec sandbox cat /workspace/myfile.txt
```

## [TOOL TO IMPLEMENT] EXECUTE

Execute an arbitrary command in the sandbox

```bash
docker exec sandbox sh -c <commmand>
```

**Note**:

- `sh -c` allows running multiple commands in sequence
- Files are created in `/workspace` since it's writable in the slim image
