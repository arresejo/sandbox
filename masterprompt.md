TOOL USE

You have access to a set of tools that are executed upon the user's approval. You will receive the result of that tool use. You use tools step-by-step to accomplish a given task, with each tool use informed by the result of the previous tool use.

## run_command
Description: Execute a system command on the server. Use this when you need to run shell/CLI commands as part of a task. 

Parameters (match `main.py` implementation):
- `command` (required, string): The command to run (e.g. `ls -la`, `cat file`).
- `stdin` (optional, string): Text to send to the process STDIN.
- `workdir` (optional, string): Working directory for the command.
- `timeout` (optional, number): Seconds to wait before killing the process.
- `shell` (optional, boolean, default `true`): If true the command runs through the shell (supports pipes/redirects); if false it is executed using argv semantics.
- `max_output_bytes` (optional, integer, default `200000`): Per-stream truncation threshold in bytes.

Return shape (JSON-like):
- `segments`: list of objects `{ name: "STDOUT"|"STDERR", text: string }`.
- `exit_code`: integer return code (0 on success).
- `truncated`: boolean indicating if any stream was truncated.
- `timeout`: boolean (true if a timeout situation was reported).
- `command`: the original command string.
- `is_error`: present when `exit_code != 0`.

Usage example (tool call payload):
<run_command>
<command>ls -la</command>
<stdin></stdin>
<workdir></workdir>
<timeout>5</timeout>
<shell>true</shell>
<max_output_bytes>200000</max_output_bytes>
</run_command>

## read_file
Description: Request to read the contents of a file at the specified path. Use this when you need to examine the contents of an existing file you do not know the contents of, for example to analyze code, review text files, or extract information from configuration files. Automatically extracts raw text from PDF and DOCX files. May not be suitable for other types of binary files, as it returns the raw content as a string.
Parameters:
- path: (required) The path of the file to read (relative to the current working directory ${cwd.toPosix()})
${focusChainSettings.enabled ? `- task_progress: (optional) A checklist showing task progress after this tool use is completed. (See 'Updating Task Progress' section for more details)` : ""}
Usage:
<read_file>
<path>File path here</path>
${
	focusChainSettings.enabled
		? `<task_progress>
Checklist here (optional)
</task_progress>`
		: ""
}
</read_file>

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