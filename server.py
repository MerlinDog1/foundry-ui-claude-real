#!/usr/bin/env python3
import base64
import json
import os
import shutil
import subprocess
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WORKING = ROOT / "working"
ASSETS = ROOT / "assets"
FOUNDRY_SCRIPTS = Path("/data/data/com.termux/files/home/.openclaw/workspace/skills/foundry/scripts")

WORKING.mkdir(parents=True, exist_ok=True)

STAGES = {
    "generated": WORKING / "generated.png",
    "styled": WORKING / "styled.png",
    "upscaled": WORKING / "upscaled.png",
    "traced_svg": WORKING / "traced.svg",
    "traced_png": WORKING / "traced.png",
}

MIME = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".svg": "image/svg+xml",
    ".json": "application/json; charset=utf-8",
}

POWER_WORDS = "Binary / 1-bit Art, No Halftones / No Gradients, CNC-ready / Laser-cut / Vector Paths"


def run(cmd):
    proc = subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "Command failed")
    return proc.stdout.strip()


def read_json(handler):
    length = int(handler.headers.get("Content-Length", "0"))
    raw = handler.rfile.read(length) if length else b"{}"
    return json.loads(raw.decode("utf-8"))


def gemini_generate_image(prompt: str, aspect: str = "1:1", resolution: str = "1K"):
    api_key = os.environ.get("GEMINI_API_KEY") or "REPLACE_WITH_YOUR_GEMINI_API_KEY"
    final_prompt = f"{prompt}. {POWER_WORDS}. {resolution}, {aspect}, woodcut style, black and white only."

    endpoint = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-2.0-flash-preview-image-generation:generateContent"
        f"?key={api_key}"
    )
    payload = {
        "contents": [{"parts": [{"text": final_prompt}]}],
        "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
    }

    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Gemini HTTP {e.code}: {detail}") from e

    candidates = data.get("candidates", [])
    for cand in candidates:
        parts = cand.get("content", {}).get("parts", [])
        for part in parts:
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and "data" in inline:
                STAGES["generated"].write_bytes(base64.b64decode(inline["data"]))
                return
    raise RuntimeError("Gemini did not return image data")


def write_binary_trace_png():
    # For PNG trace mode, keep a thresholded raster output for download/preview.
    run([
        "python",
        str(FOUNDRY_SCRIPTS / "apply_style.py"),
        str(STAGES["upscaled"]),
        str(STAGES["traced_png"]),
        "minimalist-logo",
    ])


class Handler(BaseHTTPRequestHandler):
    def _send(self, code=200, body=b"", content_type="application/json; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj).encode("utf-8"))

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        if self.path == "/":
            p = ROOT / "index.html"
            self._send(200, p.read_bytes(), MIME[".html"])
            return

        if self.path.startswith("/preview/"):
            stage = self.path.split("/preview/", 1)[1]
            lookup = {
                "generated": STAGES["generated"],
                "styled": STAGES["styled"],
                "upscaled": STAGES["upscaled"],
                "traced": STAGES["traced_svg"],
                "traced-png": STAGES["traced_png"],
            }
            f = lookup.get(stage)
            if not f or not f.exists():
                self._send(404, b"Not found", "text/plain; charset=utf-8")
                return
            self._send(200, f.read_bytes(), MIME.get(f.suffix, "application/octet-stream"))
            return

        if self.path.startswith("/download/"):
            name = self.path.split("/download/", 1)[1]
            files = {"svg": STAGES["traced_svg"], "png": STAGES["traced_png"], "generated": STAGES["generated"]}
            f = files.get(name)
            if not f or not f.exists():
                self._send(404, b"Not found", "text/plain; charset=utf-8")
                return
            self._send(200, f.read_bytes(), MIME.get(f.suffix, "application/octet-stream"))
            return

        if self.path.startswith("/assets/"):
            p = ROOT / self.path.lstrip("/")
            if p.exists() and p.is_file():
                self._send(200, p.read_bytes(), MIME.get(p.suffix, "application/octet-stream"))
                return

        if self.path in ("/app.js", "/styles.css"):
            p = ROOT / self.path.lstrip("/")
            self._send(200, p.read_bytes(), MIME.get(p.suffix, "text/plain; charset=utf-8"))
            return

        self._send(404, b"Not found", "text/plain; charset=utf-8")

    def do_POST(self):
        try:
            payload = read_json(self)

            if self.path == "/upload":
                data_url = payload.get("dataUrl", "")
                if not data_url.startswith("data:image"):
                    self._json({"ok": False, "error": "Invalid image payload"}, 400)
                    return
                b64 = data_url.split(",", 1)[1]
                STAGES["generated"].write_bytes(base64.b64decode(b64))
                self._json({"ok": True, "path": "/preview/generated"})
                return

            if self.path == "/generate":
                prompt = payload.get("prompt", "")
                aspect = payload.get("aspectRatio", "1:1")
                resolution = payload.get("resolution", "1K")
                if not prompt.strip():
                    self._json({"ok": False, "error": "Prompt required"}, 400)
                    return
                gemini_generate_image(prompt, aspect=aspect, resolution=resolution)
                self._json({"ok": True, "path": "/preview/generated"})
                return

            if self.path == "/style":
                style = payload.get("style", "woodcut")
                if not STAGES["generated"].exists():
                    self._json({"ok": False, "error": "No generated/uploaded image"}, 400)
                    return
                run([
                    "python", str(FOUNDRY_SCRIPTS / "apply_style.py"),
                    str(STAGES["generated"]), str(STAGES["styled"]), style,
                ])
                self._json({"ok": True, "path": "/preview/styled"})
                return

            if self.path == "/upscale":
                scale = int(payload.get("scale", 4))
                src = STAGES["styled"] if STAGES["styled"].exists() else STAGES["generated"]
                run([
                    "python", str(FOUNDRY_SCRIPTS / "upscale_image.py"),
                    str(src), str(STAGES["upscaled"]), "--scale", str(scale),
                ])
                self._json({"ok": True, "path": "/preview/upscaled"})
                return

            if self.path == "/trace":
                speckle = int(payload.get("speckle", 4))
                out_format = payload.get("format", "svg")
                src = STAGES["upscaled"] if STAGES["upscaled"].exists() else (STAGES["styled"] if STAGES["styled"].exists() else STAGES["generated"])
                run([
                    "python", str(FOUNDRY_SCRIPTS / "trace_vector.py"),
                    str(src), str(STAGES["traced_svg"]), "--bw", "--filter-speckle", str(speckle),
                ])
                if out_format == "png":
                    write_binary_trace_png()
                    self._json({"ok": True, "path": "/preview/traced-png", "download": "/download/png"})
                else:
                    self._json({"ok": True, "path": "/preview/traced", "download": "/download/svg"})
                return

            if self.path == "/reset":
                for p in STAGES.values():
                    if p.exists():
                        p.unlink()
                self._json({"ok": True})
                return

            self._json({"ok": False, "error": "Unknown endpoint"}, 404)
        except Exception as e:
            self._json({"ok": False, "error": str(e)}, 500)


def main():
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8787"))
    print(f"Foundry UI server: http://{host}:{port}")
    ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    main()
