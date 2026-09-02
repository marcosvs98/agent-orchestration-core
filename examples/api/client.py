from __future__ import annotations

import json
from types import TracebackType
from typing import Any, Dict, Final, List, Literal, Mapping, Sequence
from uuid import uuid4

import httpx

DEFAULT_TIMEOUT: Final[httpx.Timeout] = httpx.Timeout(connect=5.0, read=180.0, write=30.0, pool=5.0)


class ApiError(RuntimeError):
    def __init__(self, method: str, url: str, status_code: int, body: str) -> None:
        self.method = method
        self.url = url
        self.status_code = status_code
        self.body = body
        super().__init__(f"{method} {url} -> {status_code}\n{body}")


class ApiClient:
    def __init__(self, base_url: str, token: str, *, verbose: bool = True) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.verbose = verbose
        self.step_number = 0
        self.client = httpx.Client(timeout=DEFAULT_TIMEOUT)

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> "ApiClient":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> Literal[False]:
        self.close()
        return False

    def set_token(self, token: str) -> None:
        self.token = token

    def _headers(self, idempotent: bool) -> Dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}",
        }
        if idempotent:
            headers["Idempotency-Key"] = str(uuid4())
        return headers

    def request(
        self,
        method: str,
        path: str,
        *,
        label: str = "",
        json_body: Any = None,
        params: Mapping[str, Any] | None = None,
        idempotent: bool = False,
        expect: Sequence[int] = (200, 201, 202, 204),
    ) -> Any:
        self.step_number += 1
        url = f"{self.base_url}{path}"
        content = None if json_body is None else json.dumps(json_body).encode("utf-8")

        response = self.client.request(
            method,
            url,
            content=content,
            params=dict(params) if params else None,
            headers=self._headers(idempotent),
        )

        if self.verbose:
            title = label or f"{method} {path}"
            marker = "ok " if response.status_code in expect else "FAIL"
            print(f"  {marker} [{self.step_number:>2}] {title:<52} {response.status_code}")

        if response.status_code not in expect:
            raise ApiError(method, url, response.status_code, response.text[:2000])

        if response.status_code == 204 or not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            return response.text

    def stream_sse(
        self,
        path: str,
        json_body: Any,
        *,
        label: str = "",
        expect: Sequence[int] = (200,),
    ) -> List[Dict[str, Any]]:
        self.step_number += 1
        url = f"{self.base_url}{path}"
        headers = self._headers(idempotent=True)
        headers["Accept"] = "text/event-stream"

        events: List[Dict[str, Any]] = []
        with self.client.stream(
            "POST",
            url,
            content=json.dumps(json_body).encode("utf-8"),
            headers=headers,
        ) as response:
            if self.verbose:
                title = label or f"POST {path}"
                marker = "ok " if response.status_code in expect else "FAIL"
                print(f"  {marker} [{self.step_number:>2}] {title:<52} {response.status_code}")
            if response.status_code not in expect:
                body = b"".join(response.iter_bytes()).decode("utf-8", "replace")
                raise ApiError("POST", url, response.status_code, body[:2000])

            event_name = ""
            data_lines: List[str] = []
            for line in response.iter_lines():
                if line.startswith("event:"):
                    event_name = line[6:].strip()
                elif line.startswith("data:"):
                    data_lines.append(line[5:].strip())
                elif not line:
                    if data_lines:
                        raw = "\n".join(data_lines)
                        try:
                            payload = json.loads(raw)
                        except ValueError:
                            payload = {"raw": raw}
                        events.append({"event": event_name, "data": payload})
                    event_name = ""
                    data_lines = []
        return events

    def post(self, path: str, json_body: Any = None, **kwargs: Any) -> Any:
        return self.request("POST", path, json_body=json_body, **kwargs)

    def patch(self, path: str, json_body: Any = None, **kwargs: Any) -> Any:
        return self.request("PATCH", path, json_body=json_body, **kwargs)

    def get(self, path: str, **kwargs: Any) -> Any:
        return self.request("GET", path, **kwargs)

    def delete(self, path: str, **kwargs: Any) -> Any:
        return self.request("DELETE", path, **kwargs)


def require_id(payload: Any, field: str, what: str) -> str:
    if not isinstance(payload, dict):
        raise SystemExit(f"{what}: expected a JSON object, got {type(payload).__name__}")
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise SystemExit(
            f"{what}: response has no usable '{field}'.\n"
            f"got keys: {sorted(payload)}\n"
            f"payload: {json.dumps(payload)[:600]}"
        )
    return value
