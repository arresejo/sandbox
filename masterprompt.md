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

## deploy_repo

Description: Deploy written files to a new GitHub repository using the `gh` CLI and push the contents the written files to it. A new repository is created.

Parameters (match `main.py` implementation):

- `repo_name` (required, string): Name for the new GitHub repository.
- `visibility` (optional, string): Either `private` or `public`. Default is `private`.
- `description` (optional, string): Description for the repository.

Return shape:

- `repo_url`: URL of the created repository.
- `status`: "success" on success.
- `stdout`: Output from the deployment process.
- `is_error` / `message` / `stderr` / `exit_code`: present on failure.

Usage example (tool call):
<deploy_repo>
<repo_name>my-repo</repo_name>
<visibility>public</visibility>
<description>Demo repo created with Mistral</description>
</deploy_repo>

Example success response (conceptual):
{
"repo_url": "https://github.com/username/my-repo",
"status": "success",
"stdout": "...gh cli output..."
}

Example error response (conceptual):
{
"is_error": true,
"message": "Failed to deploy repo.",
"exit_code": 1,
"stdout": "...",
"stderr": "..."
}

- `size`: integer bytes
- `timestamp`: ISO8601 UTC
- `is_error` / `message`: on failure

Example tool call:
<read_file>
<path>main.py</path>
</read_file>

Example success response (conceptual):
{
"path": "/workspace/main.py",
"content": "import os\n...",
"truncated": false,
"size": 1234,
"timestamp": "2025-09-13T12:34:56Z"
}

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
