# Le Bac à Sable

Add a sandbox to **Le Chat** to supercharge its capabilities. Iterate on your files and datasets directly in your sandbox and deploy your product—all from Le Chat.

Le Bac à Sable attaches a Linux container sandbox to every chat, enabling the model to create, modify, and execute files during the conversation. While Mistral Medium excels at coding tasks, the native code interpreter tool has limitations. This is especially useful when working with medium to large files or transferring them between tools.

## Examples

- Ask Le Chat to download and clean a dataset. Le Bac à Sable’s MCP provides a tool to run commands for that.  
- Build a full-stack app, iterate on the generated code, and deploy it—all from Le Chat.  
- Convert video or audio files to your desired format.  
- Expose your workspace to the internet with ngrok for quick sharing or testing.  
- Push your sandbox files directly to a new GitHub repository.  
- …and more 🚀  

---

## Installation

```bash
uv python install
uv sync --locked
```

## Usage

Start the server on port 3000:

```bash
uv run main.py
```

---

## Available Tools

### Command & File Tools

1. **`run_command`**  
   Execute arbitrary shell commands with structured output inside the sandbox container.  
   - Parameters: `command`, `stdin`, `timeout`, `shell`, `max_output_bytes`.  
   - Response: `segments`, `exit_code`, `truncated`, `timeout`, `is_error`.  

   Example:  
   ```python
   run_command("ls -1")
   ```

2. **`write_to_file`**  
   Create or overwrite a text file with provided content. Parent directories created automatically.  
   - Parameters: `path`, `content`.  
   - Response: `path`, `bytes_written`, `created`, `timestamp`.  

3. **`replace_in_file`**  
   Perform multiple literal (non-regex) search/replace operations in a file.  
   - Parameters: `path`, `replacements`.  
   - Response: `changed`, `replacements`, `timestamp`.  

4. **`read_file`**  
   Read full textual contents of a file inside the sandbox.  
   - Parameters: `path`.  
   - Response: `content`, `size`, `timestamp`, `truncated`.  

5. **`list_file`**  
   List (non-recursive) directory entries.  
   - Parameters: `path` (default `"."`).  
   - Response: `entries`, `count`, `timestamp`.  

---

### Sandbox Management

6. **`spawn_sandbox`**  
   Ensures a long-lived detached docker container exists.  
   - Parameters: `name`, `image`, `recreate`.  
   - Response: `container_id`, `created`, `message`.  

7. **`list_files`**  
   List files in `/workspace` inside the sandbox container.  

---

### Collaboration & Sharing

8. **`push_files`** *(experimental, may be disabled)*  
   Push files in the sandbox to a new GitHub repository.  
   - Parameters: `repo_name`.  
   - Response: `repo_url`, `status`, `stdout` or error fields.  

9. **`get_workspace_public_url`**  
   Start `http.server` + `ngrok` inside the sandbox to expose `/workspace` over the internet.  
   - Response: `url` if successful.  

---

### Prompt

`command_help` – concise guidance for using `run_command` including parameters and error semantics.

---

## Running the Inspector (Optional)

### Optional Requirement (Only for Inspector UI)

If you want to use the MCP Inspector UI for debugging/introspection you need Node.js (tested with >=22). The Python MCP server itself does NOT depend on Node.js.

### Quick Start (UI mode)

```bash
npx @modelcontextprotocol/inspector
```

The inspector server will start up and the UI will be accessible at [http://localhost:6274](http://localhost:6274).

Configure test connection:  
- Transport Type: **Streamable HTTP**  
- URL: **http://127.0.0.1:3000/mcp**

---

## Development

### Adding New Tools

To add a new tool, modify `main.py`:

```python
@mcp.tool(
    title="Your Tool Name",
    description="Tool Description for the LLM",
)
async def new_tool(
    tool_param1: str = Field(description="The description of param1"),
    tool_param2: float = Field(description="The description of param2")
) -> str:
    # The new tool logic
    result = await some_api_call(tool_param1, tool_param2)
    return result
```

### Tests

Run minimal async tests:

```bash
uv run test_run_command.py
```

### Adding New Resources

```python
@mcp.resource(
    uri="your-scheme://{param1}/{param2}",
    description="Description of the resource",
    name="Your Resource Name",
)
def your_resource(param1: str, param2: str) -> str:
    return f"Resource content for {param1} and {param2}"
```

### Adding New Prompts

```python
@mcp.prompt("Helpful Prompt")
async def your_prompt(
    prompt_param: str = Field(description="The description of the param for the user")
) -> str:
    return f"You are a friendly assistant, help the user and don't forget to {prompt_param}."
```

---

## Docker Environment

Le Bac à Sable uses a **multi-stage Dockerfile**:

1. **Builder Stage**  
   - Based on `python:3.12-slim-bullseye`  
   - Installs build dependencies and compiles Python wheels.  

2. **Runtime Stage**  
   - Lightweight Python 3.12 slim image.  
   - Includes runtime tools:  
     - GitHub CLI (`gh`)  
     - ngrok  
     - ffmpeg  
     - curl, wget, jq, unzip, git  
   - Optional Node.js + npm (commented out).  
   - Creates a non-root `sandboxuser`.  

Exposes ports:  
- `8000` (http.server)  
- `4040` (ngrok API)  

Default CMD: `bash`  

---

## Environment Variables

- **`NGROK_AUTHTOKEN`** – Required to use `get_workspace_public_url`.  
- **`gh-api-token`** – GitHub API token (injected via headers) for `push_files`.  

---
