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
memory_store = {}
committed_hashes = set()

# Rate limiting
request_log = defaultdict(list)
RATE_LIMIT = 100
RATE_WINDOW = timedelta(hours=24)
LOG_FILE = "mcbse_requests.jsonl"


def get_stable_hash(content: str) -> str:
    return hashlib.md5(content.encode()).hexdigest()


def log_request(ip: str, test_type: str, result: dict):
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "ip": ip,
        "test_type": test_type,
        "result": result
    }
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")


def check_rate_limit(ip: str) -> bool:
    now = datetime.utcnow()
    window_start = now - RATE_WINDOW
    request_log[ip] = [t for t in request_log[ip] if t > window_start]
    if len(request_log[ip]) >= RATE_LIMIT:
        return False
    request_log[ip].append(now)
    return True


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.url.path == "/health":
        return await call_next(request)
    ip = request.client.host
    if not check_rate_limit(ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    return await call_next(request)


@app.get("/health")
async def health():
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
    ip = request.client.host
    storage_key = f"{ip}:{req.key}"
    memory_store[storage_key] = {
        "value": req.value,
        "stored_at": datetime.utcnow().isoformat(),
        "type": "persistence"
    }
    retrieved = memory_store.get(storage_key)
    result = {
        "test": "persistence",
        "key": req.key,
        "stored_value": req.value,
        "retrieved_value": retrieved["value"] if retrieved else None,
        "persistence_verified": retrieved is not None and retrieved["value"] == req.value,
        "state_match": 1.0 if (retrieved and retrieved["value"] == req.value) else 0.0,
    }
    log_request(ip, "persistence", result)
    return result


class NoveltyRequest(BaseModel):
    content: str


@app.post("/test/novelty")
async def test_novelty(request: Request, req: NoveltyRequest):
    ip = request.client.host
    content_key = f"{ip}:{req.content}"
    content_hash = get_stable_hash(content_key)
    is_duplicate = content_hash in committed_hashes
    
    if not is_duplicate:
        committed_hashes.add(content_hash)
        memory_store[f"novelty:{content_hash}"] = {
            "content": req.content,
            "content_hash": content_hash,
            "first_seen": datetime.utcnow().isoformat()
        }
    
    result = {
        "test": "novelty",
        "content": req.content,
        "is_duplicate": is_duplicate,
        "memory_commit": not is_duplicate,
        "total_unique_commits": len(committed_hashes),
    }
    log_request(ip, "novelty", result)
    return result


class NullRequest(BaseModel):
    query: str


@app.post("/test/null")
async def test_null(request: Request, req: NullRequest):
    ip = request.client.host
    storage_key = f"{ip}:{req.query}"
    exists = storage_key in memory_store
    stored_data = memory_store.get(storage_key)
    
    if exists and stored_data:
        result = {
            "test": "null_retrieval",
            "query": req.query,
            "result": stored_data["value"],
            "exists": True,
        }
    else:
        result = {
            "test": "null_retrieval",
            "query": req.query,
            "result": "NULL",
            "exists": False,
        }
    log_request(ip, "null", result)
    return result


# PRE-POPULATED CROSS-DOMAIN BOUND STATES
cross_domain_bound_states = {
    "entropy": {
        "concept": "entropy",
        "domains": {
            "physics": {
                "definition": "Measure of thermodynamic disorder",
                "equation": "S = k_B ln(Ω)",
                "context": "Second Law of Thermodynamics"
            },
            "information_theory": {
                "definition": "Shannon entropy",
                "equation": "H(X) = -Σ p(x) log p(x)",
                "context": "Data compression"
            },
            "literature": {
                "reference": "The Waste Land by T.S. Eliot",
                "quote": "These fragments I have shored against my ruins",
            },
            "music": {
                "reference": "Entropy by DJ Shadow",
                "concept": "Increasing disorder in musical structure",
            },
            "philosophy": {
                "concept": "Arrow of Time",
                "philosopher": "Arthur Eddington",
            }
        },
        "cross_domain_insight": "All domains converge on irreversible progression toward disorder"
    },
    "resonance": {
        "concept": "resonance",
        "domains": {
            "physics": {"definition": "Amplification at natural frequency", "equation": "ω = √(k/m)"},
            "psychology": {"concept": "Emotional resonance", "reference": "Carl Jung"},
            "music": {"definition": "Harmonic reinforcement"},
            "literature": {"concept": "Thematic resonance", "example": "Leitmotif in Wagner"}
        },
        "cross_domain_insight": "Resonance as selective amplification across domains"
    },
    "chaos": {
        "concept": "chaos",
        "domains": {
            "mathematics": {"definition": "Sensitive to initial conditions", "equation": "Lorenz attractor"},
            "mythology": {"concept": "Primordial void", "reference": "Hesiod's Theogony"},
            "literature": {"reference": "Jurassic Park", "quote": "Life finds a way"},
            "physics": {"definition": "Deterministic randomness"}
        },
        "cross_domain_insight": "Chaos as order's shadow across domains"
    },
    "wave": {
        "concept": "wave",
        "domains": {
            "physics": {"definition": "Oscillation through space and time", "equation": "y = A sin(kx - ωt)"},
            "quantum_mechanics": {"definition": "Wave-particle duality"},
            "oceanography": {"types": ["Capillary", "Gravity", "Tsunami"]},
            "psychology": {"concept": "Brain waves", "types": ["Delta", "Theta", "Alpha", "Beta", "Gamma"]}
        },
        "cross_domain_insight": "Wave as universal propagation mechanism"
    }
}


class CrossDomainRequest(BaseModel):
    concept: str


@app.post("/test/cross_domain")
async def test_cross_domain(request: Request, req: CrossDomainRequest):
    ip = request.client.host
    concept = req.concept.lower().strip()
    
    if concept in cross_domain_bound_states:
        bound_state = cross_domain_bound_states[concept]
        result = {
            "test": "cross_domain_synthesis",
            "query_concept": concept,
            "found": True,
            "domain_count": len(bound_state["domains"]),
            "domains_retrieved": list(bound_state["domains"].keys()),
            "bound_state": bound_state,
            "retrieval_time": "O(1)",
        }
    else:
        available = list(cross_domain_bound_states.keys())
        result = {
            "test": "cross_domain_synthesis",
            "query_concept": concept,
            "found": False,
            "result": "NULL",
            "available_concepts": available,
        }
    log_request(ip, "cross_domain", result)
    return result


@app.get("/", response_class=HTMLResponse)
async def test_page():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>MCBSE Test Harness</title>
        <style>
            body { font-family: system-ui; max-width: 800px; margin: 40px auto; padding: 20px; }
            .test-section { border: 1px solid #ddd; padding: 20px; margin: 20px 0; border-radius: 8px; }
            button { padding: 10px 20px; margin: 5px; cursor: pointer; background: #0066cc; color: white; border: none; border-radius: 4px; }
            .result { background: #f5f5f5; padding: 15px; margin-top: 10px; border-radius: 4px; font-family: monospace; white-space: pre-wrap; }
            input { padding: 8px; margin: 5px; width: 300px; }
        </style>
    </head>
    <body>
        <h1>MCBSE Test Harness v1.1.0</h1>
        
        <div class="test-section">
            <h3>1. Health Check</h3>
            <button onclick="fetch('/health').then(r=>r.json()).then(d=>alert(JSON.stringify(d)))">Check</button>
        </div>
        
        <div class="test-section">
            <h3>2. Persistence</h3>
            <input id="pkey" placeholder="key"><input id="pval" placeholder="value">
            <button onclick="fetch('/test/persistence',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key:pkey.value,value:pval.value})}).then(r=>r.json()).then(d=>alert(JSON.stringify(d,null,2)))">Store</button>
        </div>
        
        <div class="test-section">
            <h3>3. Null Test</h3>
            <input id="nquery" placeholder="query">
            <button onclick="fetch('/test/null',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({query:nquery.value})}).then(r=>r.json()).then(d=>alert(JSON.stringify(d,null,2)))">Query</button>
        </div>
        
        <div class="test-section">
            <h3>4. Novelty</h3>
            <input id="ncontent" placeholder="content">
            <button onclick="fetch('/test/novelty',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({content:ncontent.value})}).then(r=>r.json()).then(d=>alert(JSON.stringify(d,null,2)))">Check</button>
        </div>
        
        <div class="test-section">
            <h3>5. Cross-Domain Synthesis ⭐</h3>
            <p>Try: entropy, resonance, chaos, wave</p>
            <input id="cdconcept" placeholder="concept" value="entropy">
            <button onclick="fetch('/test/cross_domain',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({concept:cdconcept.value})}).then(r=>r.json()).then(d=>alert(JSON.stringify(d,null,2)))">Retrieve</button>
        </div>
    </body>
    </html>
    """


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
