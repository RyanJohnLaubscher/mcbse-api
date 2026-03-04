from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime, timedelta
import json
import hashlib
from collections import defaultdict

app = FastAPI(title="MCBSE Test Harness", version="1.1.0")

# CORS for browser access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# UNIFIED in-memory storage for MCBSE simulation
# All endpoints read/write to this single store
memory_store = {}
committed_hashes = set()  # For novelty detection - tracks committed content

# Rate limiting: IP -> list of timestamps
request_log = defaultdict(list)
RATE_LIMIT = 100  # requests per day (increased for testing)
RATE_WINDOW = timedelta(hours=24)

# Request logging to JSON file
LOG_FILE = "mcbse_requests.jsonl"


def get_stable_hash(content: str) -> str:
    """Generate stable hash across Python sessions"""
    return hashlib.md5(content.encode()).hexdigest()


def log_request(ip: str, test_type: str, result: dict):
    """Log request to JSON file"""
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "ip": ip,
        "test_type": test_type,
        "result": result
    }
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")


def check_rate_limit(ip: str) -> bool:
    """Check if IP has exceeded rate limit"""
    now = datetime.utcnow()
    window_start = now - RATE_WINDOW
    
    # Filter to recent requests only
    request_log[ip] = [t for t in request_log[ip] if t > window_start]
    
    if len(request_log[ip]) >= RATE_LIMIT:
        return False
    
    request_log[ip].append(now)
    return True


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Apply rate limiting to all endpoints except health"""
    if request.url.path == "/health":
        return await call_next(request)
    
    ip = request.client.host
    if not check_rate_limit(ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded: 10 requests per 24 hours")
    
    return await call_next(request)


@app.get("/health")
async def health():
    """System status check"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.1.0",
        "storage_keys": len(memory_store),
        "committed_hashes": len(committed_hashes)
    }


class PersistenceRequest(BaseModel):
    key: str
    value: str


@app.post("/test/persistence")
async def test_persistence(request: Request, req: PersistenceRequest):
    """
    Test persistence: store value, then verify it can be retrieved.
    Uses UNIFIED storage shared with /test/null endpoint.
    """
    ip = request.client.host
    storage_key = f"{ip}:{req.key}"
    
    # Phase 1: Store in unified memory
    memory_store[storage_key] = {
        "value": req.value,
        "stored_at": datetime.utcnow().isoformat(),
        "type": "persistence"
    }
    
    # Phase 2: Retrieve from SAME unified storage
    retrieved = memory_store.get(storage_key)
    
    result = {
        "test": "persistence",
        "key": req.key,
        "stored_value": req.value,
        "retrieved_value": retrieved["value"] if retrieved else None,
        "persistence_verified": retrieved is not None and retrieved["value"] == req.value,
        "state_match": 1.0 if (retrieved and retrieved["value"] == req.value) else 0.0,
        "storage_key_used": storage_key
    }
    
    log_request(ip, "persistence", result)
    return result


class NoveltyRequest(BaseModel):
    content: str


@app.post("/test/novelty")
async def test_novelty(request: Request, req: NoveltyRequest):
    """
    Test novelty detection: repeated identical input should not cause
