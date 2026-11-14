"""Serve only the independent preview and explicitly approved repository evidence."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSETS = ROOT / "docs/pilot-baseline"
EXAMPLES = ROOT / "backend/docs/examples"
ROUTES = {
    "/": (HERE / "index.html", "text/html"),
    "/style.css": (HERE / "style.css", "text/css"),
    "/app.js": (HERE / "app.js", "text/javascript"),
    "/model.mjs": (HERE / "model.mjs", "text/javascript"),
    "/data/example.json": (EXAMPLES / "recommendation_alajuela.json", "application/json"),
    "/data/request.json": (EXAMPLES / "recommendation_request_alajuela.json", "application/json"),
    "/data/crops.json": (EXAMPLES / "crops.json", "application/json"),
    "/evidence.md": (ASSETS / "README.md", "text/plain"),
}
for name in ("sentinel-2b-2024-03-25-overview.png", "worldcover-2021.png", "soilgrids-soc-0-5cm.png", "ftw-2025-over-sentinel-2024.png"):
    ROUTES[f"/assets/{name}"] = (ASSETS / name, "image/png")


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        entry = ROUTES.get(urlsplit(self.path).path)
        if not entry or not entry[0].is_file():
            self.send_error(404, "Not an available preview asset")
            return
        payload = entry[0].read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", entry[1])
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
        self.end_headers()
        self.wfile.write(payload)


def create_server(port):
    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    with create_server(args.port) as server:
        print(f"Offline preview: http://127.0.0.1:{server.server_port} (Ctrl+C to stop)", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
