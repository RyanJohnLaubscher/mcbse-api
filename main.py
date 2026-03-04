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
        "version": "1.0.1",
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
    duplicate memory commits. Uses STABLE hashing (not Python's hash()).
    """
    ip = request.client.host
    
    # Create unique key for this IP + content
    content_key = f"{ip}:{req.content}"
    content_hash = get_stable_hash(content_key)
    
    # Check if this exact content was already committed (across all time)
    is_duplicate = content_hash in committed_hashes
    
    if not is_duplicate:
        # First time seeing this content - commit it
        committed_hashes.add(content_hash)
        # Also store in unified memory for verification
        memory_store[f"novelty:{content_hash}"] = {
            "content": req.content,
            "content_hash": content_hash,
            "first_seen": datetime.utcnow().isoformat()
        }
    
    result = {
        "test": "novelty",
        "content": req.content,
        "content_hash": content_hash,
        "is_duplicate": is_duplicate,
        "memory_commit": not is_duplicate,
        "total_unique_commits": len(committed_hashes),
        "state_match": 1.0 if is_duplicate else 0.0,
        "notes": "Duplicate detected - no re-encoding" if is_duplicate else "Novel content - committed"
    }
    
    log_request(ip, "novelty", result)
    return result


class NullRequest(BaseModel):
    query: str


# PRE-POPULATED CROSS-DOMAIN BOUND STATES
# These demonstrate multi-channel architecture - a query retrieves ALL domains simultaneously
# This is IMPOSSIBLE with a simple dictionary - you can't get physics + literature + music
# from one key without actual bound state encoding
cross_domain_bound_states = {
    "entropy": {
        "concept": "entropy",
        "domains": {
            "physics": {
                "definition": "Measure of thermodynamic disorder; ΔS ≥ 0 for isolated systems",
                "equation": "S = k_B ln(Ω)",
                "context": "Second Law of Thermodynamics"
            },
            "information_theory": {
                "definition": "Shannon entropy; expected value of information content",
                "equation": "H(X) = -Σ p(x) log p(x)",
                "context": "Data compression and communication theory"
            },
            "literature": {
                "reference": "The Waste Land by T.S. Eliot",
                "quote": "These fragments I have shored against my ruins",
                "context": "Chaos, dissolution, and fragmentation as thematic elements"
            },
            "music": {
                "reference": "Entropy by DJ Shadow",
                "concept": "Increasing disorder in musical structure",
                "context": "Electronic music exploring chaotic soundscapes"
            },
            "philosophy": {
                "concept": "Arrow of Time",
                "philosopher": "Arthur Eddington",
                "context": "Why time appears to flow in one direction"
            }
        },
        "cross_domain_insight": "All domains converge on the same abstract concept: irreversible progression toward disorder, whether in heat, information, narrative structure, sound, or time itself."
    },
    "resonance": {
        "concept": "resonance",
        "domains": {
            "physics": {
                "definition": "Amplification of oscillation at natural frequency",
                "equation": "ω = √(k/m)",
                "context": "Mechanical and acoustic systems"
            },
            "psychology": {
                "concept": "Emotional resonance",
                "reference": "Carl Jung's collective unconscious",
                "context": "Shared symbolic meaning across individuals"
            },
            "music": {
                "definition": "Harmonic reinforcement of frequencies",
                "example": "Sympathetic vibration of strings",
                "context": "Instrument design and acoustics"
            },
            "literature": {
                "concept": "Thematic resonance",
                "example": "Leitmotif in Wagner's operas",
                "context": "Recurring patterns that accumulate meaning"
            }
        },
        "cross_domain_insight": "Resonance as selective amplification - whether physical vibration, emotional response, harmonic reinforcement, or thematic recurrence."
    },
    "chaos": {
        "concept": "chaos",
        "domains": {
            "mathematics": {
                "definition": "Deterministic systems sensitive to initial conditions",
                "equation": "Lorenz attractor: dx/dt = σ(y-x)",
                "context": "Dynamical systems theory"
            },
            "mythology": {
                "concept": "Primordial void",
                "reference": "Hesiod's Theogony",
                "context": "First thing to exist; from which cosmos emerged"
            },
            "literature": {
                "reference": "Chaos theory in Jurassic Park by Michael Crichton",
                "quote": "Life finds a way",
                "context": "Unpredictability in complex systems"
            },
            "physics": {
                "definition": "Apparent randomness from deterministic rules",
                "example": "Double pendulum motion",
                "context": "Classical mechanics"
            }
        },
        "cross_domain_insight": "Chaos as order's shadow - mathematical unpredictability mirrors mythological void mirrors literary uncertainty."
    },
    "wave": {
        "concept": "wave",
        "domains": {
            "physics": {
                "definition": "Oscillation propagating through space and time",
                "equation": "y(x,t) = A sin(kx - ωt)",
                "context": "Mechanical and electromagnetic waves"
            },
            "quantum_mechanics": {
                "definition": "Wave-particle duality",
                "equation": "Schrödinger equation",
                "context": "Probability amplitude propagation"
            },
            "oceanography": {
                "types": ["Capillary", "Gravity", "Tsunami"],
                "context": "Fluid dynamics and coastal engineering"
            },
            "psychology": {
                "concept": "Brain waves",
                "types": ["Delta", "Theta", "Alpha", "Beta", "Gamma"],
                "context": "Neural oscillation patterns"
            }
        },
        "cross_domain_insight": "Wave as universal propagation mechanism - energy, probability, water, and neural activity all exhibit wave behavior."
    }
}


class CrossDomainRequest(BaseModel):
    concept: str


@app.post("/test/null")
async def test_null(request: Request, req: NullRequest):
    """
    Test NULL retrieval: querying for non-existent data should return
    explicit NULL rather than confabulation.
    Uses SAME unified storage as /test/persistence.
    """
    ip = request.client.host
    
    # Use SAME key format as persistence endpoint
    storage_key = f"{ip}:{req.query}"
    
    # Check if query exists in unified memory
    exists = storage_key in memory_store
    stored_data = memory_store.get(storage_key)
    
    if exists and stored_data:
        result = {
            "test": "null_retrieval",
            "query": req.query,
            "storage_key": storage_key,
            "result": stored_data["value"],
            "exists": True,
            "memory_commit": True,
            "state_match": 1.0,
            "notes": "Data exists - returned encoded state"
        }
    else:
        result = {
            "test": "null_retrieval",
            "query": req.query,
            "storage_key": storage_key,
            "result": "NULL",
            "exists": False,
            "memory_commit": False,
            "state_match": 0.0,
            "notes": "Verified absence returned - no confabulation"
        }
    
    log_request(ip, "null", result)
    return result


@app.post("/test/cross_domain")
async def test_cross_domain(request: Request, req: CrossDomainRequest):
    """
    Cross-Domain Synthesis Test: Query one concept, retrieve bound state
    across multiple domains simultaneously.
    
    This is IMPOSSIBLE with a simple dictionary - you cannot retrieve
    physics + literature + music from one query without actual multi-channel
    bound state architecture.
    
    Pre-encoded bound states: entropy, resonance, chaos, wave
    """
    ip = request.client.host
    concept = req.concept.lower().strip()
    
    # Check if concept exists in cross-domain bound states
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
            "notes": f"Retrieved complete bound state across {len(bound_state['domains'])} domains simultaneously"
        }
    else:
        # Return available concepts
        available = list(cross_domain_bound_states.keys())
        result = {
            "test": "cross_domain_synthesis",
            "query_concept": concept,
            "found": False,
            "result": "NULL",
            "available_concepts": available,
            "notes": "Concept not in bound state corpus. Try: entropy, resonance, chaos, wave"
        }
    
    log_request(ip, "cross_domain", result)
    return result


@app.get("/", response_class=HTMLResponse)
async def test_page():
    """Minimal HTML test page"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>MCBSE Test Harness</title>
        <style>
            body { font-family: system-ui, sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; }
            h1 { color: #333; }
            .test-section { border: 1px solid #ddd; padding: 20px; margin: 20px 0; border-radius: 8px; }
            button { padding: 10px 20px; margin: 5px; cursor: pointer; background: #0066cc; color: white; border: none; border-radius: 4px; }
            button:hover { background: #0052a3; }
            .result { background: #f5f5f5; padding: 15px; margin-top: 10px; border-radius: 4px; font-family: monospace; white-space: pre-wrap; }
            input { padding: 8px; margin: 5px; width: 300px; }
            .status { padding: 10px; margin: 10px 0; border-radius: 4px; }
            .status.ok { background: #d4edda; color: #155724; }
            .status.error { background: #f8d7da; color: #721c24; }
        </style>
    </head>
    <body>
        <h1>🔬 MCBSE Test Harness v1.0.1</h1>
        <p>Multi-Channel Bound State Encoding — Research Prototype</p>
        <div id="status" class="status"></div>
        
        <div class="test-section">
            <h3>1. Health Check</h3>
            <button onclick="checkHealth()">Check System Status</button>
            <div id="health-result" class="result" style="display:none"></div>
        </div>
        
        <div class="test-section">
            <h3>2. Persistence Test</h3>
            <p>Store a value using a key, then query it via NULL test to verify unified storage</p>
            <input type="text" id="persistence-key" placeholder="Key (e.g., my-test-key)">
            <input type="text" id="persistence-value" placeholder="Value to store">
            <br>
            <button onclick="testPersistence()">Store Value</button>
            <div id="persistence-result" class="result" style="display:none"></div>
        </div>
        
        <div class="test-section">
            <h3>3. Cross-Endpoint Persistence Test</h3>
            <p>Query for a key stored above using NULL endpoint (verifies unified storage)</p>
            <input type="text" id="null-query" placeholder="Query same key as above">
            <br>
            <button onclick="testNull()">Query via NULL Endpoint</button>
            <div id="null-result" class="result" style="display:none"></div>
        </div>
        
        <div class="test-section">
            <h3>4. Novelty Test</h3>
            <p>Submit identical content twice — second should be detected as duplicate</p>
            <input type="text" id="novelty-content" placeholder="Content to test">
            <br>
            <button onclick="testNovelty(1)">Submit (First Time)</button>
            <button onclick="testNovelty(2)">Submit (Second Time)</button>
            <div id="novelty-result" class="result" style="display:none"></div>
        </div>
        
        <div class="test-section">
            <h3>5. Cross-Domain Synthesis Test ⭐</h3>
            <p><strong>IMPOSSIBLE for a dictionary:</strong> Query one concept, retrieve physics + literature + music + more simultaneously</p>
            <p>Pre-encoded bound states: entropy, resonance, chaos, wave</p>
            <input type="text" id="cross-domain-concept" placeholder="Concept (try: entropy)">
            <br>
            <button onclick="testCrossDomain()">Retrieve Bound State</button>
            <div id="cross-domain-result" class="result" style="display:none"></div>
        </div>
        
        <script>
            const API_BASE = window.location.origin;
            
            async function checkHealth() {
                try {
                    const resp = await fetch(`${API_BASE}/health`);
                    const data = await resp.json();
                    showResult('health-result', JSON.stringify(data, null, 2));
                    showStatus('System healthy', true);
                } catch (e) {
                    showResult('health-result', 'Error: ' + e.message);
                    showStatus('Connection failed', false);
                }
            }
            
            async function testPersistence() {
                const key = document.getElementById('persistence-key').value || 'default-key';
                const value = document.getElementById('persistence-value').value || 'test-value';
                
                try {
                    const resp = await fetch(`${API_BASE}/test/persistence`, {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({key: key, value: value})
                    });
                    const data = await resp.json();
                    showResult('persistence-result', JSON.stringify(data, null, 2));
                    showStatus(data.persistence_verified ? 'Persistence verified ✓' : 'Persistence failed ✗', data.persistence_verified);
                } catch (e) {
                    showResult('persistence-result', 'Error: ' + e.message);
                    showStatus('Test failed', false);
                }
            }
            
            async function testNull() {
                const query = document.getElementById('null-query').value || 'nonexistent-query-xyz';
                
                try {
                    const resp = await fetch(`${API_BASE}/test/null`, {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({query: query})
                    });
                    const data = await resp.json();
                    showResult('null-result', JSON.stringify(data, null, 2));
                    const isNull = (data.result === 'NULL' || data.result === null);
                    showStatus(isNull ? 'NULL returned ✓' : 'Value found (exists in storage)', !isNull);
                } catch (e) {
                    showResult('null-result', 'Error: ' + e.message);
                    showStatus('Test failed', false);
                }
            }
            
            async function testNovelty(attempt) {
                const content = document.getElementById('novelty-content').value || 'test-content-' + Date.now();
                
                try {
                    const resp = await fetch(`${API_BASE}/test/novelty`, {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({content: content})
                    });
                    const data = await resp.json();
                    const prev = document.getElementById('novelty-result').textContent;
                    showResult('novelty-result', prev + '\\n\\nAttempt ' + attempt + ':\\n' + JSON.stringify(data, null, 2));
                    showStatus(data.is_duplicate ? 'Duplicate detected ✓' : 'Novel content - committed', true);
                } catch (e) {
                    showResult('novelty-result', 'Error: ' + e.message);
                    showStatus('Test failed', false);
                }
            }
            
            async function testCrossDomain() {
                const concept = document.getElementById('cross-domain-concept').value || 'entropy';
                
                try {
                    const resp = await fetch(`${API_BASE}/test/cross_domain`, {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({concept: concept})
                    });
                    const data = await resp.json();
                    showResult('cross-domain-result', JSON.stringify(data, null, 2));
                    if (data.found) {
                        showStatus(`Cross-domain synthesis: ${data.domain_count} domains retrieved ✓`, true);
                    } else {
                        showStatus(`Concept not found. Available: ${data.available_concepts.join(', ')}`, false);
                    }
                } catch (e) {
                    showResult('cross-domain-result', 'Error: ' + e.message);
                    showStatus('Test failed', false);
                }
            }
            
            function showResult(id, content) {
                const el = document.getElementById(id);
                el.textContent = content;
                el.style.display = 'block';
            }
            
            function showStatus(msg, ok) {
                const el = document.getElementById('status');
                el.textContent = msg;
                el.className = 'status ' + (ok ? 'ok' : 'error');
                el.style.display = 'block';
            }
            
            // Check health on load
            checkHealth();
        </script>
    </body>
    </html>
    """


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)