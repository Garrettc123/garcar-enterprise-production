"""
Garcar Base Contract — FastAPI Sidecar
=======================================
Universal health, meta, metrics, and event endpoints for all Garcar systems.
Runs as a sidecar or embedded in each system.
Part of Continuum Grid v1.
"""

from __future__ import annotations

import os
import time
import uuid
import json
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
import httpx

@dataclass
class ContractConfig:
    system_id: str = os.environ.get("GARCAR_SYSTEM_ID", "unknown-system")
    system_name: str = os.environ.get("GARCAR_SYSTEM_NAME", "Unknown System")
    layer: str = os.environ.get("GARCAR_LAYER", "infrastructure")
    version: str = os.environ.get("GARCAR_VERSION", "0.1.0")
    tier: str = os.environ.get("GARCAR_TIER", "prototype")
    supabase_url: str = os.environ.get("SUPABASE_URL", "")
    supabase_anon_key: str = os.environ.get("SUPABASE_ANON_KEY", "")
    supabase_service_key: str = os.environ.get("SUPABASE_SERVICE_KEY", "")
    start_time: float = time.time()
    request_count: int = 0
    error_count: int = 0
    event_batch_size: int = 10
    event_flush_interval: float = 5.0

CONFIG = ContractConfig()

class HealthResponse(BaseModel):
    status: str = "healthy"
    system_id: str
    system_name: str
    layer: str
    version: str
    tier: str
    uptime_seconds: float
    timestamp: str
    checks: Dict[str, bool] = {}

class MetaResponse(BaseModel):
    system_id: str
    system_name: str
    layer: str
    version: str
    tier: str
    capabilities: List[str] = []
    apis: List[Dict[str, str]] = []
    events_published: List[str] = []
    events_consumed: List[str] = []
    health_endpoints: List[str] = []
    dependencies: List[str] = []
    owners: List[str] = []
    manifest_url: str = ""
    repository_url: str = ""

class MetricsResponse(BaseModel):
    system_id: str
    uptime_seconds: float
    request_count: int
    error_count: int
    error_rate: float
    memory_usage_mb: float
    cpu_percent: float
    custom: Dict[str, Any] = {}

class EventPublishRequest(BaseModel):
    event_type: str = Field(..., pattern=r'^[a-z]+\.[a-z_]+$')
    payload: Dict[str, Any] = {}
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None
    trace_id: Optional[str] = None

class EventPublishResponse(BaseModel):
    event_id: str
    event_type: str
    timestamp: str
    accepted: bool

class EventConsumeRequest(BaseModel):
    event_types: List[str]
    limit: int = 100

class EventBusClient:
    def __init__(self, config: ContractConfig):
        self.config = config
        self.client: Optional[httpx.AsyncClient] = None
        self.buffer: List[Dict] = []
        self._flush_task: Optional[asyncio.Task] = None

    async def start(self):
        if not self.config.supabase_url or not self.config.supabase_service_key:
            print("WARNING: Supabase not configured, event bus disabled")
            return
        self.client = httpx.AsyncClient(
            base_url=f"{self.config.supabase_url}/rest/v1",
            headers={
                "apikey": self.config.supabase_service_key,
                "Authorization": f"Bearer {self.config.supabase_service_key}",
                "Content-Type": "application/json",
                "Prefer": "return=representation",
            },
            timeout=10.0,
        )
        self._flush_task = asyncio.create_task(self._periodic_flush())

    async def stop(self):
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        await self.flush()
        if self.client:
            await self.client.aclose()

    async def publish(self, event: EventPublishRequest) -> EventPublishResponse:
        event_id = str(uuid.uuid4())
        trace_id = event.trace_id or str(uuid.uuid4())
        record = {
            "id": event_id,
            "event_type": event.event_type,
            "source_system": self.config.system_id,
            "payload": event.payload,
            "correlation_id": event.correlation_id,
            "causation_id": event.causation_id,
            "trace_id": trace_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "processed": False,
            "metadata": {},
        }
        if self.client:
            try:
                resp = await self.client.post("/garcar_events", json=record)
                resp.raise_for_status()
                return EventPublishResponse(event_id=event_id, event_type=event.event_type, timestamp=record["timestamp"], accepted=True)
            except Exception as e:
                print(f"Event publish failed: {e}")
                self.buffer.append(record)
        else:
            self.buffer.append(record)
        return EventPublishResponse(event_id=event_id, event_type=event.event_type, timestamp=record["timestamp"], accepted=False)

    async def consume(self, request: EventConsumeRequest) -> List[Dict]:
        if not self.client:
            return []
        try:
            params = {
                "processed": "eq.false",
                "event_type": f"in.({','.join(request.event_types)})",
                "source_system": f"neq.{self.config.system_id}",
                "order": "timestamp.asc",
                "limit": str(request.limit),
            }
            resp = await self.client.get("/garcar_events", params=params)
            resp.raise_for_status()
            events = resp.json()
            if events:
                ids = [e["id"] for e in events]
                await self.client.post("/rpc/mark_events_processed", json={"p_ids": ids})
            return events
        except Exception as e:
            print(f"Event consume failed: {e}")
            return []

    async def flush(self):
        if not self.buffer or not self.client:
            return
        to_send = self.buffer[:self.config.event_batch_size]
        try:
            resp = await self.client.post("/garcar_events", json=to_send)
            resp.raise_for_status()
            self.buffer = self.buffer[len(to_send):]
        except Exception as e:
            print(f"Event flush failed: {e}")

    async def _periodic_flush(self):
        while True:
            await asyncio.sleep(self.config.event_flush_interval)
            await self.flush()

EVENT_BUS = EventBusClient(CONFIG)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await EVENT_BUS.start()
    yield
    await EVENT_BUS.stop()

app = FastAPI(title=f"{CONFIG.system_name} — Garcar Base Contract", version=CONFIG.version, lifespan=lifespan)

@app.middleware("http")
async def count_requests(request: Request, call_next):
    CONFIG.request_count += 1
    try:
        return await call_next(request)
    except Exception:
        CONFIG.error_count += 1
        raise

@app.get("/health", response_model=HealthResponse)
async def health():
    checks = {"process": True, "event_bus": EVENT_BUS.client is not None, "supabase": bool(CONFIG.supabase_url and CONFIG.supabase_service_key)}
    return HealthResponse(
        status="healthy" if all(checks.values()) else "degraded",
        system_id=CONFIG.system_id, system_name=CONFIG.system_name, layer=CONFIG.layer,
        version=CONFIG.version, tier=CONFIG.tier,
        uptime_seconds=time.time() - CONFIG.start_time,
        timestamp=datetime.now(timezone.utc).isoformat(), checks=checks,
    )

@app.get("/ready")
async def ready():
    checks = {"event_bus": EVENT_BUS.client is not None, "supabase": bool(CONFIG.supabase_url and CONFIG.supabase_service_key)}
    if all(checks.values()):
        return {"ready": True, "checks": checks}
    raise HTTPException(status_code=503, detail={"ready": False, "checks": checks})

@app.get("/meta", response_model=MetaResponse)
async def meta():
    manifest = {}
    if os.path.exists("garcar.manifest.json"):
        try:
            with open("garcar.manifest.json") as f:
                manifest = json.load(f)
        except Exception:
            pass
    return MetaResponse(
        system_id=manifest.get("system_id", CONFIG.system_id),
        system_name=manifest.get("display_name", CONFIG.system_name),
        layer=manifest.get("layer", CONFIG.layer),
        version=manifest.get("version", CONFIG.version),
        tier=manifest.get("tier", CONFIG.tier),
        capabilities=manifest.get("capabilities", []),
        apis=manifest.get("apis", []),
        events_published=manifest.get("events_published", []),
        events_consumed=manifest.get("events_consumed", []),
        health_endpoints=manifest.get("health_endpoints", [f"https://{CONFIG.system_id}.garcar.internal/health"]),
        dependencies=manifest.get("dependencies", []),
        owners=manifest.get("owners", ["Garrettc123"]),
        manifest_url=f"https://{CONFIG.system_id}.garcar.internal/garcar.manifest.json",
        repository_url=f"https://github.com/Garrettc123/{CONFIG.system_id}",
    )

@app.get("/metrics", response_model=MetricsResponse)
async def metrics():
    try:
        import psutil
        process = psutil.Process()
        mem = process.memory_info().rss / 1024 / 1024
        cpu = process.cpu_percent()
    except Exception:
        mem, cpu = 0.0, 0.0
    return MetricsResponse(
        system_id=CONFIG.system_id,
        uptime_seconds=time.time() - CONFIG.start_time,
        request_count=CONFIG.request_count,
        error_count=CONFIG.error_count,
        error_rate=CONFIG.error_count / max(CONFIG.request_count, 1),
        memory_usage_mb=mem, cpu_percent=cpu, custom={},
    )

@app.post("/events", response_model=EventPublishResponse)
async def publish_event(event: EventPublishRequest):
    return await EVENT_BUS.publish(event)

@app.post("/events/consume")
async def consume_events(request: EventConsumeRequest):
    events = await EVENT_BUS.consume(request)
    return {"events": events, "count": len(events)}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
