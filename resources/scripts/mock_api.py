from __future__ import annotations

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def catch_all(request: Request, path: str):
    body = None
    try:
        body = await request.json()
    except Exception:
        pass

    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "message": "Request received successfully",
            "path": f"/{path}",
            "method": request.method,
            "received_body": body,
        },
    )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=3000)
