#!/usr/bin/env python3
"""
AI Agent Network Hub - Production Ready
Garcar Enterprise
"""

import os
import asyncio
import logging
from datetime import datetime
from typing import Dict, List
import asyncpg
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import uuid

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Get allowed origins from environment
allowed_origins_str = os.getenv('ALLOWED_ORIGINS', 'http://localhost:3000,http://localhost:5000')
allowed_origins = [origin.strip() for origin in allowed_origins_str.split(',')]

app = FastAPI(
    title="Garcar AI Agent Hub",
    description="Distributed AI Agent Orchestration",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

class Agent(BaseModel):
    agent_id: str
    type: str
    system: str
    endpoint: str
    capabilities: List[str]

class Task(BaseModel):
    task_name: str
    task_type: str
    agent_id: str = None

class AgentHub:
    def __init__(self):
        self.pool = None
    
    async def connect(self):
        """Connect to database"""
        self.pool = await asyncpg.create_pool(
            host=os.getenv('DB_HOST', 'localhost'),
            port=int(os.getenv('DB_PORT', 5432)),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD'),
            database=os.getenv('DB_NAME', 'revenue_aggregator'),
            min_size=3,
            max_size=10
        )
        logger.info("Agent Hub database connection established")
    
    async def register_agent(self, agent: Agent) -> str:
        """Register new AI agent"""
        async with self.pool.acquire() as conn:
            agent_uuid = str(uuid.uuid4())
            await conn.execute(
                """
                INSERT INTO ai_agents 
                (id, agent_id, type, system, endpoint, capabilities, status)
                VALUES ($1, $2, $3, $4, $5, $6, 'active')
                """,
                agent_uuid, agent.agent_id, agent.type, agent.system,
                agent.endpoint, agent.capabilities
            )
            logger.info(f"Registered agent: {agent.agent_id}")
            return agent_uuid
    
    async def list_agents(self, status: str = 'active') -> List[Dict]:
        """List all agents"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM ai_agents WHERE status = $1",
                status
            )
            return [dict(row) for row in rows]
    
    async def assign_task(self, task: Task) -> str:
        """Assign task to agent"""
        async with self.pool.acquire() as conn:
            # Find suitable agent
            if not task.agent_id:
                agent = await conn.fetchrow(
                    """
                    SELECT id FROM ai_agents 
                    WHERE status = 'active' 
                    ORDER BY performance_score DESC 
                    LIMIT 1
                    """
                )
                if not agent:
                    raise HTTPException(404, "No available agents")
                task.agent_id = agent['id']
            
            # Create task
            task_id = str(uuid.uuid4())
            await conn.execute(
                """
                INSERT INTO agent_tasks 
                (id, agent_id, task_name, task_type, status)
                VALUES ($1, $2, $3, $4, 'pending')
                """,
                task_id, task.agent_id, task.task_name, task.task_type
            )
            logger.info(f"Task assigned: {task_id}")
            return task_id
    
    async def get_agent_performance(self) -> List[Dict]:
        """Get agent performance metrics"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM v_agent_performance ORDER BY performance_score DESC"
            )
            return [dict(row) for row in rows]

hub = AgentHub()

@app.on_event("startup")
async def startup():
    await hub.connect()
    logger.info("AI Agent Hub started")

@app.on_event("shutdown")
async def shutdown():
    if hub.pool:
        await hub.pool.close()
    logger.info("AI Agent Hub shutdown")

@app.get("/status")
async def status():
    return {
        "status": "operational",
        "service": "ai-agent-hub",
        "version": "1.0.0"
    }

@app.post("/agents/register")
async def register_agent(agent: Agent):
    agent_id = await hub.register_agent(agent)
    return {"agent_id": agent_id, "status": "registered"}

@app.get("/agents")
async def list_agents(status: str = 'active'):
    return await hub.list_agents(status)

@app.post("/tasks")
async def create_task(task: Task):
    task_id = await hub.assign_task(task)
    return {"task_id": task_id, "status": "assigned"}

@app.get("/performance")
async def agent_performance():
    return await hub.get_agent_performance()

if __name__ == "__main__":
    uvicorn.run(
        "hub:app",
        host="0.0.0.0",
        port=8081,
        log_level="info"
    )
