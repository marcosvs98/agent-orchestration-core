from __future__ import annotations

import copy
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import TracebackType
from typing import Any, Dict, Final, List, Literal
from uuid import uuid4

SPEC_PATH: Final[Path] = (
    Path(__file__).resolve().parents[2]
    / "resources"
    / "scripts"
    / "seeds"
    / "demo"
    / "openapi"
    / "demo_api.json"
)


def load_spec(public_base_url: str) -> Dict[str, Any]:
    parsed: object = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise SystemExit(f"{SPEC_PATH} is not a JSON object")
    spec: Dict[str, Any] = parsed
    spec["servers"] = [{"url": public_base_url}]
    return spec


class _ExpenseServer(ThreadingHTTPServer):
    calls: List[Dict[str, Any]]
    fail_next: int
    fail_mode: str
    spec: Dict[str, Any]


class _Handler(BaseHTTPRequestHandler):
    server: _ExpenseServer

    protocol_version = "HTTP/1.1"

    def log_message(self, *args: Any) -> None:
        return None

    def _send(self, status: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path in ("/openapi.json", "/swagger.json"):
            self._send(200, self.server.spec)
            return
        if self.path == "/__calls":
            self._send(200, {"calls": self.server.calls})
            return
        self._send(404, {"error": "not_found", "path": self.path})

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        try:
            payload = json.loads(raw) if raw else {}
        except ValueError:
            self._send(400, {"error": "invalid_json"})
            return

        if self.path.rstrip("/") != "/createExpense":
            self._send(404, {"error": "not_found", "path": self.path})
            return

        self.server.calls.append(
            {
                "path": self.path,
                "body": payload,
                "authorization": self.headers.get("Authorization"),
            }
        )

        if self.server.fail_next > 0:
            self.server.fail_next -= 1
            if self.server.fail_mode == "hangup":
                self.close_connection = True
                return
            self._send(503, {"error": "upstream_unavailable"})
            return

        self._send(200, {"expense_id": f"exp_{uuid4().hex[:12]}", "status": "created"})


class ExpenseApiStub:
    def __init__(self, host: str = "127.0.0.1", port: int = 0) -> None:
        self.host = host
        self.requested_port = port
        self.server: _ExpenseServer | None = None
        self.thread: threading.Thread | None = None

    @property
    def base_url(self) -> str:
        if self.server is None:
            raise RuntimeError("stub is not started")
        return f"http://{self.host}:{self.server.server_address[1]}"

    @property
    def openapi_url(self) -> str:
        return f"{self.base_url}/openapi.json"

    @property
    def calls(self) -> List[Dict[str, Any]]:
        if self.server is None:
            return []
        return copy.deepcopy(self.server.calls)

    def fail_next_calls(self, count: int, mode: str = "hangup") -> None:
        if self.server is None:
            raise RuntimeError("stub is not started")
        if mode not in ("hangup", "status_503"):
            raise ValueError(f"unknown failure mode {mode!r}")
        self.server.fail_next = count
        self.server.fail_mode = mode

    def start(self) -> "ExpenseApiStub":
        self.server = _ExpenseServer((self.host, self.requested_port), _Handler)
        self.server.calls = []
        self.server.fail_next = 0
        self.server.fail_mode = "hangup"
        self.server.spec = load_spec(self.base_url)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self

    def stop(self) -> None:
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
            self.server = None

    def __enter__(self) -> "ExpenseApiStub":
        return self.start()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> Literal[False]:
        self.stop()
        return False
