#!/usr/bin/env python3
"""
MPY Cross Compiler Server
=========================
A single-file Python HTTP server that serves a browser UI for compiling
.py files to .mpy using the local mpy_cross Python package.

Usage:
    python mpy_compiler_server.py

Then open your browser (it opens automatically) and drag/drop or select
multiple .py files to compile them all at once.
"""

import os
import sys
import json
import base64
import tempfile
import shutil
import webbrowser
import threading
import subprocess
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

# ---------------------------------------------------------------------------
# HTML/JS/CSS frontend (embedded so this file is self-contained)
# ---------------------------------------------------------------------------
FRONTEND = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MPY Cross Compiler</title>
<style>
:root {
  --bg: #0d1117;
  --surface: #161b22;
  --surface-hover: #1f242c;
  --border: #30363d;
  --text: #c9d1d9;
  --text-muted: #8b949e;
  --accent: #58a6ff;
  --accent-hover: #79b8ff;
  --success: #3fb950;
  --error: #f85149;
  --warning: #d29922;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: var(--bg);
  color: var(--text);
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}
header {
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  padding: 1rem 2rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
header h1 { font-size: 1.25rem; font-weight: 600; display: flex; align-items: center; gap: 0.5rem; }
header h1 .icon { color: var(--accent); }
.status-badge {
  font-size: 0.75rem;
  padding: 0.25rem 0.75rem;
  border-radius: 999px;
  background: var(--border);
  color: var(--text-muted);
  font-weight: 500;
}
.status-badge.ready { background: rgba(63,185,80,0.15); color: var(--success); }
.status-badge.error { background: rgba(248,81,73,0.15); color: var(--error); }
main {
  flex: 1;
  max-width: 960px;
  width: 100%;
  margin: 0 auto;
  padding: 2rem;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}
.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 1.5rem;
}
.card-title {
  font-size: 0.875rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
  margin-bottom: 1rem;
}
.dropzone {
  border: 2px dashed var(--border);
  border-radius: 10px;
  padding: 3rem 2rem;
  text-align: center;
  transition: all 0.2s ease;
  cursor: pointer;
}
.dropzone:hover, .dropzone.dragover {
  border-color: var(--accent);
  background: rgba(88,166,255,0.05);
}
.dropzone .icon-big { font-size: 2.5rem; margin-bottom: 1rem; color: var(--text-muted); }
.dropzone:hover .icon-big, .dropzone.dragover .icon-big { color: var(--accent); }
.dropzone p { color: var(--text-muted); font-size: 0.9375rem; }
.dropzone .hint { font-size: 0.8125rem; margin-top: 0.5rem; opacity: 0.7; }
.dropzone input[type="file"] { display: none; }
.settings-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem;
}
.field { display: flex; flex-direction: column; gap: 0.375rem; }
.field label { font-size: 0.8125rem; font-weight: 500; color: var(--text-muted); }
select, input[type="text"] {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 0.5rem 0.75rem;
  color: var(--text);
  font-size: 0.875rem;
  outline: none;
}
select:focus, input[type="text"]:focus { border-color: var(--accent); }
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 0.625rem 1.25rem;
  border-radius: 6px;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  border: none;
  transition: all 0.15s ease;
}
.btn-primary { background: var(--accent); color: #fff; }
.btn-primary:hover:not(:disabled) { background: var(--accent-hover); }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-secondary { background: var(--bg); color: var(--text); border: 1px solid var(--border); }
.btn-secondary:hover { background: var(--surface-hover); }
.btn-success { background: var(--success); color: #fff; text-decoration: none; }
.file-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  max-height: 320px;
  overflow-y: auto;
}
.file-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.75rem 1rem;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 8px;
  gap: 1rem;
}
.file-item .file-info {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  min-width: 0;
}
.file-item .file-name {
  font-size: 0.875rem;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.file-item .file-size {
  font-size: 0.75rem;
  color: var(--text-muted);
  white-space: nowrap;
}
.file-item .file-actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-shrink: 0;
}
.file-status {
  font-size: 0.75rem;
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  font-weight: 500;
  white-space: nowrap;
}
.file-status.pending { color: var(--text-muted); background: rgba(139,148,158,0.1); }
.file-status.compiling { color: var(--accent); background: rgba(88,166,255,0.1); }
.file-status.done { color: var(--success); background: rgba(63,185,80,0.1); }
.file-status.failed { color: var(--error); background: rgba(248,81,73,0.1); }
.remove-btn {
  background: none;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 1rem;
  padding: 0.25rem;
  line-height: 1;
  border-radius: 4px;
}
.remove-btn:hover { color: var(--error); background: rgba(248,81,73,0.1); }
.actions-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
}
.actions-bar .left, .actions-bar .right {
  display: flex;
  gap: 0.75rem;
  align-items: center;
}
.empty-state {
  text-align: center;
  padding: 2rem;
  color: var(--text-muted);
  font-size: 0.9375rem;
}
.log {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 1rem;
  max-height: 200px;
  overflow-y: auto;
  font-family: 'SF Mono', Monaco, Consolas, monospace;
  font-size: 0.8125rem;
  line-height: 1.6;
}
.log-entry { padding: 0.125rem 0; }
.log-entry.info { color: var(--text); }
.log-entry.success { color: var(--success); }
.log-entry.error { color: var(--error); }
.log-entry.warn { color: var(--warning); }
.hidden { display: none !important; }
.spinner {
  display: inline-block;
  width: 0.875rem;
  height: 0.875rem;
  border: 2px solid rgba(255,255,255,0.3);
  border-radius: 50%;
  border-top-color: currentColor;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
::-webkit-scrollbar { width: 8px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 4px; }
footer {
  text-align: center;
  padding: 1rem;
  font-size: 0.75rem;
  color: var(--text-muted);
  border-top: 1px solid var(--border);
}
</style>
</head>
<body>
<header>
  <h1><span class="icon">&#9889;</span> MPY Cross Compiler</h1>
  <span id="compilerStatus" class="status-badge ready">Using local mpy_cross</span>
</header>

<main>
  <div class="card">
    <div class="card-title">Upload Files</div>
    <div class="dropzone" id="dropzone">
      <div class="icon-big">&#128194;</div>
      <p>Drag &amp; drop <strong>.py</strong> files here, or click to browse</p>
      <p class="hint">Select multiple Python files to compile them all at once</p>
      <input type="file" id="fileInput" accept=".py" multiple>
    </div>
  </div>

  <div class="card">
    <div class="card-title">Compiler Settings</div>
    <div class="settings-row">
      <div class="field">
        <label for="targetArch">Target Architecture</label>
        <select id="targetArch">
          <option value="">auto (default)</option>
          <option value="x86">x86</option>
          <option value="x64">x64</option>
          <option value="armv6m">armv6m</option>
          <option value="armv7m">armv7m</option>
          <option value="armv7emsp">armv7emsp</option>
          <option value="armv7emdp">armv7emdp</option>
          <option value="xtensa">xtensa (ESP8266)</option>
          <option value="xtensawin" selected>xtensawin (ESP32 / ESP32-S3)</option>
          <option value="rv32imc">rv32imc</option>
        </select>
      </div>
      <div class="field">
        <label for="optLevel">Optimization Level</label>
        <select id="optLevel">
          <option value="0">0 - None</option>
          <option value="1">1 - Basic</option>
          <option value="2">2 - Assertions removed</option>
          <option value="3" selected>3 - Debug info removed</option>
        </select>
      </div>
    </div>
  </div>

  <div class="card" id="filesCard">
    <div class="card-title">Files to Compile</div>
    <div id="fileList" class="file-list">
      <div class="empty-state">No files selected. Drop .py files above to get started.</div>
    </div>
  </div>

  <div class="actions-bar">
    <div class="left">
      <button id="compileBtn" class="btn btn-primary" disabled>
        <span id="compileSpinner" class="spinner hidden"></span>
        <span id="compileLabel">Compile All</span>
      </button>
      <button id="clearBtn" class="btn btn-secondary" disabled>Clear All</button>
    </div>
  </div>

  <div class="card" id="logCard">
    <div class="card-title">Output Log</div>
    <div id="log" class="log"></div>
  </div>
</main>

<footer>
  Connected to local mpy_cross compiler via Python backend.
  Make sure target settings match your MicroPython firmware.
</footer>

<script>
const files = new Map();
let isCompiling = false;

const $ = id => document.getElementById(id);
const dropzone = $('dropzone');
const fileInput = $('fileInput');
const fileList = $('fileList');
const compileBtn = $('compileBtn');
const clearBtn = $('clearBtn');
const compileSpinner = $('compileSpinner');
const compileLabel = $('compileLabel');
const logEl = $('log');
const targetArch = $('targetArch');
const optLevel = $('optLevel');

function log(msg, type = 'info') {
  const entry = document.createElement('div');
  entry.className = `log-entry ${type}`;
  const time = new Date().toLocaleTimeString('en-US', { hour12: false });
  entry.textContent = `[${time}] ${msg}`;
  logEl.appendChild(entry);
  logEl.scrollTop = logEl.scrollHeight;
}

function formatBytes(bytes) {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function statusText(status) {
  switch (status) {
    case 'pending': return 'Pending';
    case 'compiling': return 'Compiling...';
    case 'done': return 'Done';
    case 'failed': return 'Failed';
    default: return status;
  }
}

function updateFileList() {
  if (files.size === 0) {
    fileList.innerHTML = '<div class="empty-state">No files selected. Drop .py files above to get started.</div>';
    compileBtn.disabled = true;
    clearBtn.disabled = true;
    return;
  }
  fileList.innerHTML = '';
  files.forEach((f, id) => {
    const item = document.createElement('div');
    item.className = 'file-item';
    let downloadLink = '';
    if (f.status === 'done' && f.result) {
      if (!f.downloadUrl) {
        f.downloadUrl = URL.createObjectURL(new Blob([Uint8Array.from(atob(f.result), c => c.charCodeAt(0))], { type: 'application/octet-stream' }));
      }
      downloadLink = `<a class="btn btn-success" href="${f.downloadUrl}" download="${f.name.replace(/\\.py$/i, '.mpy')}">Download</a>`;
    }
    item.innerHTML = `
      <div class="file-info">
        <span class="file-name">${escapeHtml(f.name)}</span>
        <span class="file-size">${formatBytes(f.size)}</span>
      </div>
      <div class="file-actions">
        <span class="file-status ${f.status}">${statusText(f.status)}</span>
        ${downloadLink}
        <button class="remove-btn" data-id="${id}" title="Remove">&times;</button>
      </div>
    `;
    fileList.appendChild(item);
  });
  fileList.querySelectorAll('.remove-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const f = files.get(btn.dataset.id);
      if (f && f.downloadUrl) { URL.revokeObjectURL(f.downloadUrl); f.downloadUrl = null; }
      files.delete(btn.dataset.id);
      updateFileList();
    });
  });
  compileBtn.disabled = isCompiling;
  clearBtn.disabled = isCompiling;
}

async function addFiles(fileListObj) {
  for (const file of fileListObj) {
    if (!file.name.endsWith('.py')) {
      log(`Skipping non-Python file: ${file.name}`, 'warn');
      continue;
    }
    const id = crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).slice(2);
    files.set(id, {
      file,
      name: file.name,
      size: file.size,
      content: null,
      status: 'pending',
      result: null,
      error: null,
      downloadUrl: null
    });
    log(`Added: ${file.name} (${formatBytes(file.size)})`);
  }
  updateFileList();
}

dropzone.addEventListener('click', () => fileInput.click());
dropzone.addEventListener('dragover', e => { e.preventDefault(); dropzone.classList.add('dragover'); });
dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));
dropzone.addEventListener('drop', e => { e.preventDefault(); dropzone.classList.remove('dragover'); addFiles(e.dataTransfer.files); });
fileInput.addEventListener('change', e => { addFiles(e.target.files); fileInput.value = ''; });

clearBtn.addEventListener('click', () => {
  files.forEach(f => { if (f.downloadUrl) { URL.revokeObjectURL(f.downloadUrl); f.downloadUrl = null; } });
  files.clear();
  updateFileList();
  log('Cleared all files.');
});

async function compileAll() {
  if (isCompiling) return;
  isCompiling = true;
  compileBtn.disabled = true;
  compileSpinner.classList.remove('hidden');
  compileLabel.textContent = 'Compiling...';
  clearBtn.disabled = true;

  const arch = targetArch.value || '';
  const opt = optLevel.value || '3';
  log(`Starting compilation: arch=${arch || 'default'}, opt=${opt}`);

  for (const [id, f] of files) {
    if (f.status === 'done') {
      f.status = 'pending';
      f.result = null;
      f.error = null;
      if (f.downloadUrl) { URL.revokeObjectURL(f.downloadUrl); f.downloadUrl = null; }
    }
    if (f.status !== 'pending' && f.status !== 'failed') continue;

    f.status = 'compiling';
    updateFileList();

    try {
      const formData = new FormData();
      formData.append('file', f.file);
      formData.append('arch', arch);
      formData.append('opt', opt);

      const response = await fetch('/compile', { method: 'POST', body: formData });
      const data = await response.json();

      if (data.success) {
        f.result = data.data;
        f.status = 'done';
        log(`Compiled: ${f.name} -> ${formatBytes(data.size)}`, 'success');
      } else {
        throw new Error(data.error || 'Compilation failed');
      }
    } catch (err) {
      f.status = 'failed';
      f.error = err.message || String(err);
      log(`Failed: ${f.name} - ${f.error}`, 'error');
    }
    updateFileList();
  }

  isCompiling = false;
  compileSpinner.classList.add('hidden');
  compileLabel.textContent = 'Compile All';
  compileBtn.disabled = false;
  clearBtn.disabled = false;

  const failed = Array.from(files.values()).filter(f => f.status === 'failed').length;
  const done = Array.from(files.values()).filter(f => f.status === 'done').length;
  if (failed === 0) log(`All ${done} file(s) compiled successfully.`, 'success');
  else log(`Done: ${done} succeeded, ${failed} failed.`, 'warn');
}

compileBtn.addEventListener('click', compileAll);
log('Ready. Select one or more .py files and click Compile All.');
</script>
</body>
</html>"""

# ---------------------------------------------------------------------------
# Server implementation
# ---------------------------------------------------------------------------

HOST = "127.0.0.1"
PORT = 0  # auto-select free port


def find_mpy_cross():
    """Return the mpy-cross executable path or None."""
    # Try mpy_cross Python module first (what the user uses)
    try:
        import mpy_cross
        # If import succeeds, we can use mpy_cross.run()
        return "mpy_cross_module"
    except ImportError:
        pass

    # Try mpy-cross binary on PATH
    exe = shutil.which("mpy-cross")
    if exe:
        return exe

    # Try mpy_cross binary on PATH (underscore variant)
    exe = shutil.which("mpy_cross")
    if exe:
        return exe

    return None


def compile_with_mpy_cross(input_path: Path, output_path: Path, arch: str, opt: str):
    """Compile a single .py file to .mpy using the local toolchain."""
    compiler = find_mpy_cross()
    if compiler is None:
        raise RuntimeError(
            "mpy_cross not found. Install it with: pip install mpy-cross"
        )

    args = []
    if arch:
        args.append(f"-march={arch}")
    if opt:
        args.append(f"-O{opt}")
    args.append("-o")
    args.append(str(output_path))
    args.append(str(input_path))

    if compiler == "mpy_cross_module":
        import mpy_cross
        # mpy_cross.run() passes args to the underlying binary
        mpy_cross.run(*args)
    else:
        result = subprocess.run(
            [compiler] + args,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr or f"mpy-cross exited with code {result.returncode}")


class RequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress default logging noise
        pass

    def _send_json(self, status_code, data):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self):
        body = FRONTEND.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            self._send_html()
        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/compile":
            self._handle_compile()
        else:
            self.send_error(404)

    def _handle_compile(self):
        content_type = self.headers.get("Content-Type", "")
        if not content_type.startswith("multipart/form-data"):
            self._send_json(400, {"success": False, "error": "Expected multipart/form-data"})
            return

        # Parse multipart form data manually (no external deps)
        boundary = content_type.split("boundary=")[1].strip()
        if boundary.startswith('"') and boundary.endswith('"'):
            boundary = boundary[1:-1]

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        parts = self._parse_multipart(body, boundary.encode())

        file_data = parts.get("file")
        arch = parts.get("arch", b"").decode("utf-8")
        opt = parts.get("opt", b"3").decode("utf-8")

        if not file_data:
            self._send_json(400, {"success": False, "error": "No file provided"})
            return

        tmp_dir = Path(tempfile.mkdtemp(prefix="mpy_compile_"))
        try:
            input_path = tmp_dir / "input.py"
            output_path = tmp_dir / "input.mpy"
            input_path.write_bytes(file_data)

            compile_with_mpy_cross(input_path, output_path, arch, opt)

            mpy_bytes = output_path.read_bytes()
            encoded = base64.b64encode(mpy_bytes).decode("ascii")

            self._send_json(
                200,
                {
                    "success": True,
                    "data": encoded,
                    "size": len(mpy_bytes),
                },
            )
        except Exception as exc:
            self._send_json(500, {"success": False, "error": str(exc)})
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def _parse_multipart(self, body: bytes, boundary: bytes):
        """Minimal multipart parser returning dict of field_name -> bytes."""
        result = {}
        delimiter = b"--" + boundary
        parts = body.split(delimiter)
        for part in parts:
            part = part.strip(b"\r\n")
            if not part or part == b"--":
                continue
            header_end = part.find(b"\r\n\r\n")
            if header_end == -1:
                continue
            headers = part[:header_end].decode("utf-8", errors="replace")
            data = part[header_end + 4 :]
            # Remove trailing \r\n before the boundary
            if data.endswith(b"\r\n"):
                data = data[:-2]

            # Find field name
            name = None
            for line in headers.split("\r\n"):
                if line.lower().startswith("content-disposition"):
                    for token in line.split(";"):
                        token = token.strip()
                        if token.startswith("name="):
                            name = token[5:].strip('"')
            if name:
                result[name] = data
        return result


def main():
    compiler = find_mpy_cross()
    if compiler is None:
        print("=" * 60)
        print("ERROR: mpy_cross not found!")
        print("=" * 60)
        print("Install it with:  pip install mpy-cross")
        print("Or ensure 'mpy-cross' binary is on your PATH.")
        print("=" * 60)
        sys.exit(1)

    # Ensure we can actually import/use it
    if compiler == "mpy_cross_module":
        print("Found compiler: mpy_cross (Python module)")
    else:
        print(f"Found compiler: {compiler}")

    server = HTTPServer((HOST, PORT), RequestHandler)
    actual_port = server.server_address[1]
    url = f"http://{HOST}:{actual_port}"

    print(f"\nServer running at {url}")
    print("Press Ctrl+C to stop.\n")

    # Open browser after a short delay
    threading.Timer(0.5, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
