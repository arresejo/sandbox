# sandbox_api.py
from fastapi import FastAPI
from pydantic import BaseModel
from pathlib import Path
import subprocess, base64

app = FastAPI()
ROOT = Path("/workspace").resolve()
ROOT.mkdir(parents=True, exist_ok=True)

def sh(cmd: str, stdin: str = ""):
    p = subprocess.Popen(["/bin/sh", "-lc", cmd],
                         cwd=str(ROOT),
                         stdin=subprocess.PIPE if stdin else None,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    out, err = p.communicate(stdin if stdin else None)
    return {"exit_code": p.returncode, "stdout": out or "", "stderr": err or ""}

@app.get("/list")
def list_files():
    entries = []
    for p in sorted(ROOT.iterdir()):
        entries.append({
            "name": p.name + ("/" if p.is_dir() else ""),
            "type": "directory" if p.is_dir() else "file",
            "size": p.stat().st_size if p.is_file() else None
        })
    return {"path": str(ROOT), "entries": entries, "count": len(entries)}

class RunReq(BaseModel):
    command: str
    stdin: str | None = ""
@app.post("/run")
def run(req: RunReq):
    return sh(req.command, req.stdin or "")

class WriteReq(BaseModel):
    path: str
    content_b64: str
@app.post("/write")
def write(req: WriteReq):
    dest = (ROOT / req.path).resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)
    data = base64.b64decode(req.content_b64)
    dest.write_bytes(data)
    return {"path": str(dest), "bytes_written": len(data), "created": True}

class ReplaceReq(BaseModel):
    path: str
    replacements: list[dict]
@app.post("/replace")
def replace(req: ReplaceReq):
    f = (ROOT / req.path).resolve()
    if not f.exists():
        return {"is_error": True, "message": "File does not exist"}
    original = f.read_text(encoding="utf-8")
    modified = original
    applied = []
    for i, r in enumerate(req.replacements):
        s = r.get("search"); t = r.get("replace", "")
        if s is None:
            applied.append({"index": i, "status": "skipped", "reason": "missing search"})
            continue
        if s not in modified:
            applied.append({"index": i, "status": "not-found"})
            continue
        c = modified.count(s)
        modified = modified.replace(s, t)
        applied.append({"index": i, "status": "replaced", "occurrences": c})
    changed = modified != original
    if changed:
        f.write_text(modified, encoding="utf-8")
    return {"path": str(f), "changed": changed, "replacements": applied}

@app.get("/read")
def read_file(path: str):
    f = (ROOT / path).resolve()
    if not f.exists():
        return {"is_error": True, "message": "File not found"}
    return {"path": str(f), "content": f.read_text(encoding="utf-8"), "truncated": False}