#!/usr/bin/env python3
"""
MPY Cross Compiler Backend
==========================
Minimal HTTP server that serves mpy_compiler.html and compiles .py -> .mpy
using the locally installed mpy_cross Python package.

Usage:
    python mpy_compiler_backend.py

Then open http://localhost:8765 in your browser.
"""

import json
import base64
import tempfile
import shutil
import webbrowser
import threading
import subprocess
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

HOST = "127.0.0.1"
PORT = 8765
HTML_FILE = Path(__file__).parent / "mpy_compiler.html"


def find_mpy_cross():
    """Return 'mpy_cross_module' if the Python package is available,
    otherwise the path to an mpy-cross binary, or None."""
    try:
        import mpy_cross  # noqa: F401
        return "mpy_cross_module"
    except ImportError:
        pass
    for name in ("mpy-cross", "mpy_cross"):
        exe = shutil.which(name)
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
    args.extend(["-o", str(output_path), str(input_path)])

    if compiler == "mpy_cross_module":
        import mpy_cross
        proc = mpy_cross.run(*args)
        rc = proc.wait()
        if rc != 0:
            stderr = proc.stderr.read() if proc.stderr else None
            raise RuntimeError(stderr or f"mpy-cross exited with code {rc}")
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
        pass

    def _send_json(self, status_code, data):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        try:
            if self.path in ("/", "/index.html"):
                if not HTML_FILE.exists():
                    self.send_error(404, "mpy_compiler.html not found")
                    return
                body = HTML_FILE.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                self.send_header("Pragma", "no-cache")
                self.send_header("Expires", "0")
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_error(404)
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            pass  # Client closed connection early — ignore

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        try:
            if self.path == "/compile":
                self._handle_compile()
            else:
                self.send_error(404)
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            pass  # Client closed connection early — ignore

    def _handle_compile(self):
        content_type = self.headers.get("Content-Type", "")
        if not content_type.startswith("multipart/form-data"):
            self._send_json(400, {"success": False, "error": "Expected multipart/form-data"})
            return

        boundary = content_type.split("boundary=")[1].strip().strip('"')
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
            data = part[header_end + 4:]
            if data.endswith(b"\r\n"):
                data = data[:-2]

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
        raise SystemExit(1)

    if compiler == "mpy_cross_module":
        print("Found compiler: mpy_cross (Python module)")
    else:
        print(f"Found compiler: {compiler}")

    server = ThreadingHTTPServer((HOST, PORT), RequestHandler)
    url = f"http://{HOST}:{PORT}"

    print(f"\nServer running at {url}")
    print("Press Ctrl+C to stop.\n")

    threading.Timer(0.5, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
