import base64
import json
import os
from datetime import datetime
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import Response
import uvicorn

try:
    from opentelemetry.proto.collector.trace.v1 import trace_service_pb2
    from opentelemetry.proto.collector.logs.v1 import logs_service_pb2
    from opentelemetry.proto.collector.metrics.v1 import metrics_service_pb2
    from google.protobuf.json_format import MessageToDict
    PROTOBUF_AVAILABLE = True
except ImportError:
    PROTOBUF_AVAILABLE = False

app = FastAPI()

LOG_DIR = Path(__file__).parent / "langfuse_logs"
LOG_DIR.mkdir(exist_ok=True)

TARGET_URL = os.getenv("LANGFUSE_TARGET_URL", "https://us.cloud.langfuse.com")
HTTP_CLIENT = httpx.AsyncClient(timeout=30.0)


def decode_protobuf_trace(data: bytes) -> dict | None:
    if not PROTOBUF_AVAILABLE:
        return None
    
    formats = [
        ("trace", trace_service_pb2.ExportTraceServiceRequest),
        ("logs", logs_service_pb2.ExportLogsServiceRequest),
        ("metrics", metrics_service_pb2.ExportMetricsServiceRequest),
    ]
    
    for format_name, message_class in formats:
        try:
            message = message_class()
            message.ParseFromString(data)
            decoded = MessageToDict(message)
            decoded["_format"] = format_name
            return decoded
        except Exception:
            continue
    
    return None


def sanitize_filename(name: str) -> str:
    import re
    sanitized = re.sub(r'[^a-zA-Z0-9_-]', '_', name)
    return sanitized[:32] if len(sanitized) > 32 else sanitized


def save_trace(data: dict | bytes, endpoint: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    
    if isinstance(data, bytes):
        decoded = decode_protobuf_trace(data)
        if decoded:
            trace_id = "unknown"
            format_type = decoded.get("_format", "unknown")
            
            if format_type == "trace" and decoded.get("resourceSpans"):
                spans = decoded["resourceSpans"][0].get("scopeSpans", [])
                if spans and spans[0].get("spans"):
                    first_span = spans[0]["spans"][0]
                    trace_id_raw = first_span.get("traceId", "unknown")
                    if isinstance(trace_id_raw, bytes):
                        trace_id = trace_id_raw.hex()[:16]
                    elif isinstance(trace_id_raw, str):
                        if len(trace_id_raw) > 16:
                            trace_id = trace_id_raw[:16]
                        elif len(trace_id_raw) == 32:
                            trace_id = trace_id_raw[:16]
                        else:
                            trace_id = trace_id_raw
            
            trace_id = sanitize_filename(str(trace_id))
            filename = f"{timestamp}_{trace_id}.json"
            filepath = LOG_DIR / filename
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "endpoint": endpoint,
                "format": f"protobuf_decoded_{format_type}",
                "data": decoded,
            }
        else:
            filename = f"{timestamp}_protobuf_raw.json"
            filepath = LOG_DIR / filename
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "endpoint": endpoint,
                "format": "protobuf_raw",
                "data_base64": base64.b64encode(data).decode("utf-8"),
                "size_bytes": len(data),
            }
    else:
        trace_id_raw = data.get("trace", {}).get("id") or data.get("id", "unknown")
        trace_id = sanitize_filename(str(trace_id_raw))[:8]
        filename = f"{timestamp}_{trace_id}.json"
        filepath = LOG_DIR / filename
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "endpoint": endpoint,
            "format": "json",
            "data": data,
        }
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(log_entry, f, indent=2, ensure_ascii=False)


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def proxy_reverse(path: str, request: Request):
    target_url = f"{TARGET_URL}/{path}"

    body = None
    if request.method in ["POST", "PUT", "PATCH"]:
        raw_body = await request.body()
        if raw_body:
            try:
                body_dict = json.loads(raw_body.decode("utf-8"))
                save_trace(body_dict, f"/{path}")
                body = body_dict
            except (json.JSONDecodeError, UnicodeDecodeError):
                save_trace(raw_body, f"/{path}")
                body = raw_body

    headers = dict(request.headers)
    headers.pop("host", None)
    headers.pop("content-length", None)

    try:
        response = await HTTP_CLIENT.request(
            method=request.method,
            url=target_url,
            headers=headers,
            content=body if isinstance(body, bytes) else None,
            json=body if isinstance(body, dict) else None,
            params=dict(request.query_params),
        )
        
        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=dict(response.headers),
        )
    except Exception as e:
        return Response(
            content=json.dumps({"error": str(e)}).encode(),
            status_code=500,
            media_type="application/json",
        )


@app.get("/health")
async def health():
    return {"status": "ok", "log_dir": str(LOG_DIR), "target_url": TARGET_URL}


if __name__ == "__main__":
    port = int(os.getenv("LANGFUSE_PROXY_PORT", "3000"))
    print(f"Langfuse Proxy running on http://0.0.0.0:{port}")
    print(f"Proxying to: {TARGET_URL}")
    print(f"Logs will be saved to: {LOG_DIR}")
    uvicorn.run(app, host="0.0.0.0", port=port)
