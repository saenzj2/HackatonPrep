"""Offline localhost preview checks; only an ephemeral loopback socket is used."""
import importlib.util
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

SPEC = importlib.util.spec_from_file_location("preview", Path(__file__).with_name("serve.py"))
preview = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(preview)


class PreviewTests(unittest.TestCase):
    def test_http_allowlist_and_assets(self):
        server = preview.create_server(0)
        self.assertEqual(server.server_address[0], "127.0.0.1")
        worker = threading.Thread(target=server.serve_forever)
        worker.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            for route in preview.ROUTES:
                with urlopen(base + route) as response:
                    self.assertEqual(response.status, 200)
                    self.assertIn("default-src 'none'", response.headers["Content-Security-Policy"])
                    self.assertGreater(len(response.read()), 0)
            for route in ("/.env", "/backend/.env", "/../README.md", "/%2e%2e/README.md", "/assets/", "/data/missing.json"):
                with self.assertRaises(HTTPError) as error:
                    urlopen(base + route)
                self.assertEqual(error.exception.code, 404)
            with self.assertRaises(HTTPError) as error:
                urlopen(Request(base + "/", method="POST", data=b"not persisted"))
            self.assertEqual(error.exception.code, 501)
        finally:
            server.shutdown()
            worker.join()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
