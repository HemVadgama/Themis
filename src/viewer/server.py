"""Small read-only local HTTP service for packaged viewer assets."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
import json
import mimetypes
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import webbrowser

from src.viewer.model import ViewerArtifactError, load_run, load_target


STATIC_ROOT = files("src.viewer").joinpath("static")


def _json_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


class ViewerRequestHandler(BaseHTTPRequestHandler):
    manifest = None
    allowed_run_paths = set()

    def log_message(self, format_string, *args):
        return

    def _send(self, status, body, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store" if content_type.startswith("application/json") else "public, max-age=3600")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; connect-src 'self'")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/manifest":
            self._send(200, _json_bytes(self.manifest), "application/json; charset=utf-8")
            return
        if parsed.path == "/api/run":
            requested = parse_qs(parsed.query).get("path", [""])[0]
            resolved = str(Path(requested).expanduser().resolve()) if requested else ""
            if resolved not in self.allowed_run_paths:
                self._send(403, _json_bytes({"error": "Run path is outside the selected viewer target."}), "application/json; charset=utf-8")
                return
            try:
                self._send(200, _json_bytes(load_run(resolved)), "application/json; charset=utf-8")
            except ViewerArtifactError as error:
                self._send(422, _json_bytes({"error": str(error)}), "application/json; charset=utf-8")
            return

        relative = "index.html" if parsed.path in {"", "/"} else parsed.path.lstrip("/")
        if relative not in {"index.html", "app.js", "temporal.js", "styles.css"}:
            self._send(404, b"Not found", "text/plain; charset=utf-8")
            return
        resource = STATIC_ROOT.joinpath(relative)
        try:
            body = resource.read_bytes()
        except (FileNotFoundError, OSError):
            self._send(404, b"Viewer asset not found", "text/plain; charset=utf-8")
            return
        content_type = mimetypes.guess_type(relative)[0] or "application/octet-stream"
        self._send(200, body, f"{content_type}; charset=utf-8")


def create_server(target, compare=None, host="127.0.0.1", port=0):
    manifest = load_target(target, compare=compare)
    allowed = set()
    if manifest["kind"] == "sweep":
        allowed = {record["run_path"] for record in manifest["records"] if record.get("run_path")}
    handler = type("BoundViewerRequestHandler", (ViewerRequestHandler,), {"manifest": manifest, "allowed_run_paths": allowed})
    return ThreadingHTTPServer((host, port), handler)


def serve_viewer(target, compare=None, host="127.0.0.1", port=0, open_browser=True):
    server = create_server(target, compare=compare, host=host, port=port)
    actual_host, actual_port = server.server_address[:2]
    browser_host = "127.0.0.1" if actual_host in {"0.0.0.0", "::"} else actual_host
    url = f"http://{browser_host}:{actual_port}/"
    print(f"Themis viewer: {url}")
    print(f"Artifacts: {Path(target).expanduser().resolve()}")
    print("Press Ctrl-C to stop.")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nViewer stopped.")
    finally:
        server.server_close()
