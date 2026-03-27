from __future__ import annotations

import json
import os
import re
import sys
import uuid
from pathlib import Path

import httpx

COLLECTION = Path(__file__).resolve().parents[1] / "collections" / "aoc.postman_collection.json"


def load_vars_from_collection(obj: dict, bearer_override: str | None = None) -> dict[str, str]:
    out: dict[str, str] = {}
    for v in obj.get("variable") or []:
        k = v.get("key")
        if k:
            out[k] = str(v.get("value") or "")
    token = (bearer_override or "").strip()
    if not token:
        token = os.environ.get("DEMO_BEARER_TOKEN", "").strip()
    if token:
        out["bearerToken"] = token
    return out


def subst_all(s: str, vars_: dict[str, str]) -> str:
    prev = None
    while prev != s:
        prev = s
        for k, v in vars_.items():
            s = s.replace(f"{{{{{k}}}}}", v)
    return s


def build_url(url_obj: dict, vars_: dict[str, str]) -> str:
    raw = subst_all(url_obj.get("raw") or "", vars_)
    for vdef in url_obj.get("variable") or []:
        key = vdef.get("key") or ""
        if not key:
            continue
        val = subst_all(str(vdef.get("value") or ""), vars_)
        raw = raw.replace(f":{key}", val)
    return raw


def apply_test_script(
    exec_lines: list[str], data: object, vars_: dict[str, str]
) -> None:
    if not isinstance(data, dict):
        return
    text = "\n".join(exec_lines)

    def setv(k: str, val: object) -> None:
        if val is not None and val != "":
            vars_[k] = str(val)

    for m in re.finditer(
        r"pm\.collectionVariables\.set\('([^']+)',\s*data\.(\w+)\)", text
    ):
        field = m.group(2)
        if field in data:
            setv(m.group(1), data[field])

    if re.search(r"data\.tools\[0\]\.id", text) and data.get("tools"):
        t0 = data["tools"][0]
        if isinstance(t0, dict) and t0.get("id"):
            setv("tool_config_id", t0["id"])

    if re.search(r"data\.access_token", text) and data.get("access_token"):
        setv("bearerToken", data["access_token"])


def collect_demo_requests(
    items: list, prefix: str = ""
) -> list[tuple[str, dict]]:
    out: list[tuple[str, dict]] = []
    for it in items:
        name = it.get("name") or ""
        if "item" in it and "request" not in it:
            out.extend(collect_demo_requests(it["item"], f"{prefix}{name}/"))
            continue
        if "request" in it:
            out.append((prefix + name, it))
    return out


def main() -> int:
    bearer_override: str | None = None
    if len(sys.argv) > 1 and sys.argv[1].strip():
        bearer_override = sys.argv[1].strip()
    elif os.environ.get("DEMO_BEARER_TOKEN", "").strip():
        bearer_override = os.environ["DEMO_BEARER_TOKEN"].strip()
    elif os.environ.get("DEMO_BEARER_TOKEN_FILE"):
        bearer_override = Path(
            os.environ["DEMO_BEARER_TOKEN_FILE"]
        ).read_text().strip()

    obj = json.loads(COLLECTION.read_text())
    if not bearer_override:
        for v in obj.get("variable") or []:
            if v.get("key") == "bearerToken":
                bearer_override = str(v.get("value") or "").strip()
                break
    if not bearer_override:
        print(
            "No bearer token: argv[1], DEMO_BEARER_TOKEN, DEMO_BEARER_TOKEN_FILE, "
            "or collection variable bearerToken",
            file=sys.stderr,
        )
        return 1

    vars_ = load_vars_from_collection(obj, bearer_override=bearer_override)
    vars_["demo_run_suffix"] = uuid.uuid4().hex[:12]
    demo_root = next(i for i in obj["item"] if i.get("name") == "demo")
    flat = collect_demo_requests(demo_root.get("item") or [])

    base = vars_.get("baseUrl", "http://localhost:8000").rstrip("/")
    print(f"demo requests: {len(flat)} base={base}")

    failures = 0
    with httpx.Client(timeout=120.0, follow_redirects=True) as client:
        for full_name, it in flat:
            req = it["request"]
            method = (req.get("method") or "GET").upper()
            url = build_url(req.get("url") or {}, vars_)
            headers = {
                h["key"]: subst_all(h.get("value") or "", vars_)
                for h in req.get("header") or []
            }
            auth = req.get("auth") or {}
            if auth.get("type") == "bearer":
                for b in auth.get("bearer") or []:
                    if b.get("key") == "token":
                        tok = subst_all(str(b.get("value") or ""), vars_)
                        headers["Authorization"] = f"Bearer {tok}"
                        break
            body_obj = req.get("body") or {}
            body: str | None = None
            if body_obj.get("mode") == "raw" and body_obj.get("raw"):
                body = subst_all(body_obj["raw"], vars_)
                headers.setdefault("Content-Type", "application/json")

            try:
                r = client.request(
                    method, url, headers=headers, content=body.encode() if body else None
                )
            except httpx.RequestError as e:
                print(f"FAIL {full_name}: {e}")
                return 1

            ok = 200 <= r.status_code < 300
            status = "OK" if ok else "FAIL"
            print(f"{status} {r.status_code} {method} {full_name}")

            if not ok:
                print(r.text[:2000])
                return 1

            data = None
            ct = r.headers.get("content-type", "")
            if "application/json" in ct and r.text:
                try:
                    data = r.json()
                except json.JSONDecodeError:
                    data = None

            for ev in it.get("event") or []:
                if ev.get("listen") == "test":
                    scr = ev.get("script") or {}
                    exec_lines = scr.get("exec") or []
                    if exec_lines:
                        apply_test_script(exec_lines, data, vars_)

    print("all demo steps passed")
    return failures


if __name__ == "__main__":
    raise SystemExit(main())
