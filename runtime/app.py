from contextlib import asynccontextmanager
from datetime import datetime, timezone
import os
import time
from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from prometheus_client import Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST

STARTED = time.time()
RUNS = Counter('garcar_agent_runs_total', 'Agent runs', ['status'])
HEARTBEAT_AGE = Gauge('garcar_agent_heartbeat_age_seconds', 'Age of worker heartbeat', ['worker_id'])

def now(): return datetime.now(timezone.utc).isoformat()

@asynccontextmanager
async def lifespan(app):
    app.state.worker_heartbeat = None
    app.state.external_actions_enabled = os.getenv('EXTERNAL_ACTIONS_ENABLED', 'false').lower() == 'true'
    yield

app = FastAPI(title='Garcar Agent Runtime', version='0.1.0', lifespan=lifespan)

@app.get('/healthz')
def healthz():
    return {'status': 'ok', 'timestamp': now(), 'uptime_seconds': round(time.time() - STARTED, 2)}

@app.get('/readyz')
def readyz():
    database_configured = bool(os.getenv('DATABASE_URL'))
    queue_configured = bool(os.getenv('REDIS_URL'))
    if not database_configured or not queue_configured:
        raise HTTPException(503, {'status': 'not_ready', 'database_configured': database_configured, 'queue_configured': queue_configured})
    return {'status': 'ready', 'timestamp': now(), 'external_actions_enabled': app.state.external_actions_enabled}

@app.post('/internal/heartbeat/{worker_id}')
def heartbeat(worker_id: str):
    app.state.worker_heartbeat = {'worker_id': worker_id, 'at': time.time(), 'timestamp': now()}
    HEARTBEAT_AGE.labels(worker_id=worker_id).set(0)
    return {'status': 'recorded'}

@app.get('/runtime/status')
def runtime_status():
    heartbeat = app.state.worker_heartbeat
    age = None if not heartbeat else round(time.time() - heartbeat['at'], 2)
    if heartbeat: HEARTBEAT_AGE.labels(worker_id=heartbeat['worker_id']).set(age)
    return {'api': 'online', 'worker': heartbeat, 'heartbeat_age_seconds': age, 'external_actions_enabled': app.state.external_actions_enabled}

@app.post('/runs/test')
def test_run():
    RUNS.labels(status='completed').inc()
    return {'status': 'completed', 'mode': 'safe_test', 'timestamp': now()}

@app.get('/metrics')
def metrics():
    return PlainTextResponse(generate_latest().decode(), media_type=CONTENT_TYPE_LATEST)
