from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from datetime import datetime, timedelta
from typing import Optional
import json
import os
import time

app = FastAPI(title="MCBSE API", version="1.0.0")

# In-memory storage
storage = {}
seen_values = set()
request_log = {}

LOG_FILE = "mcbse_requests.jsonl"

# Rate limiting: 10 requests per 24 hours per IP
RATE_LIMIT = 100
RATE_WINDOW = 86400  # 24 hours in seconds


def check_rate_limit(ip: str):
    now = time.time()
    if ip not in request_log:
        request_log[ip] = []
    # Clean old entries
    request_log[ip] = [t for t in request_log[ip] if now - t < RATE_WINDOW]
    if len(request_log[ip]) >= RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Max 10 requests per 24 hours.")
    request_log[ip].append(now)


def log_request(ip: str, endpoint: str, payload: dict = None):
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "ip": ip,
        "endpoint": endpoint,
        "payload": payload
    }
    try:
        with open(LOG_FILE, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


class PersistenceRequest(BaseModel):
    key: str
    value: str


class NoveltyRequest(BaseModel):
    value: str


class NullRequest(BaseModel):
    key: str


@app.get("/health")
async def health(request: Request):
    ip = request.client.host
    check_rate_limit(ip)
    log_request(ip, "/health")
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "storage_keys": len(storage),
        "seen_values": len(seen_values)
    }


@app.post("/test/persistence")
async def test_persistence(request: Request, body: PersistenceRequest):
    ip = request.client.host
    check_rate_limit(ip)
    log_request(ip, "/test/persistence", body.dict())
    storage[body.key] = body.value
    retrieved = storage.get(body.key)
    return {
        "stored": True,
        "key": body.key,
        "value_stored": body.value,
        "value_retrieved": retrieved,
        "match": body.value == retrieved
    }


@app.post("/test/novelty")
async def test_novelty(request: Request, body: NoveltyRequest):
    ip = request.client.host
    check_rate_limit(ip)
    log_request(ip, "/test/novelty", body.dict())
    is_duplicate = body.value in seen_values
    if not is_duplicate:
        seen_values.add(body.value)
    return {
        "value": body.value,
        "is_duplicate": is_duplicate,
        "action": "skipped (already seen)" if is_duplicate else "registered as new",
        "total_seen": len(seen_values)
    }


@app.post("/test/null")
async def test_null(request: Request, body: NullRequest):
    ip = request.client.host
    check_rate_limit(ip)
    log_request(ip, "/test/null", body.dict())
    result = storage.get(body.key)
    return {
        "key": body.key,
        "value": result,
        "exists": result is not None
    }


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    ip = request.client.host
    check_rate_limit(ip)
    log_request(ip, "/")
    html = """
<!DOCTYPE html>
<html>
<head>
    <title>MCBSE API Test Page</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; background: #1a1a2e; color: #e0e0e0; }
        h1 { color: #00d4ff; }
        .btn { background: #00d4ff; color: #1a1a2e; border: none; padding: 12px 24px; margin: 8px; cursor: pointer; border-radius: 6px; font-size: 14px; font-weight: bold; }
        .btn:hover { background: #00b8d9; }
        #output { background: #16213e; padding: 20px; border-radius: 8px; margin-top: 20px; white-space: pre-wrap; font-family: monospace; min-height: 100px; border: 1px solid #00d4ff33; }
        .section { margin: 20px 0; padding: 15px; background: #16213e; border-radius: 8px; border: 1px solid #ffffff11; }
        input { padding: 8px 12px; margin: 4px; border-radius: 4px; border: 1px solid #00d4ff55; background: #0f3460; color: #e0e0e0; }
    </style>
</head>
<body>
    <h1>MCBSE API Test Page</h1>
    <p>Interactive test interface for all API endpoints.</p>
    <div class="section">
        <h3>Health Check</h3>
        <button class="btn" onclick="testHealth()">Check Health</button>
    </div>
    <div class="section">
        <h3>Persistence Test</h3>
        <input id="pKey" placeholder="Key" value="test_key">
        <input id="pValue" placeholder="Value" value="hello_world">
        <button class="btn" onclick="testPersistence()">Store & Verify</button>
    </div>
    <div class="section">
        <h3>Novelty Test</h3>
        <input id="nValue" placeholder="Value" value="unique_item_1">
        <button class="btn" onclick="testNovelty()">Check Novelty</button>
    </div>
    <div class="section">
        <h3>Null Test</h3>
        <input id="nullKey" placeholder="Key" value="nonexistent_key">
        <button class="btn" onclick="testNull()">Query Key</button>
    </div>
    <h3>Response Output:</h3>
    <div id="output">Click a button to test an endpoint...</div>
    <script>
        const out = document.getElementById('output');
        async function testHealth() { const r = await fetch('/health'); out.textContent = JSON.stringify(await r.json(), null, 2); }
        async function testPersistence() { const r = await fetch('/test/persistence', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({key: document.getElementById('pKey').value, value: document.getElementById('pValue').value}) }); out.textContent = JSON.stringify(await r.json(), null, 2); }
        async function testNovelty() { const r = await fetch('/test/novelty', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({value: document.getElementById('nValue').value}) }); out.textContent = JSON.stringify(await r.json(), null, 2); }
        async function testNull() { const r = await fetch('/test/null', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({key: document.getElementById('nullKey').value}) }); out.textContent = JSON.stringify(await r.json(), null, 2); }
    </script>
</body>
</html>
"""
    return HTMLResponse(content=html)


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
