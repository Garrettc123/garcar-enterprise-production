#!/usr/bin/env python3
"""
Universal Revenue Aggregator - Production Ready
Garcar Enterprise
"""

import os
import asyncio
import logging
from datetime import datetime
from typing import Dict, List
import aiohttp
import asyncpg
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Garcar Revenue Aggregator",
    description="Universal Revenue Tracking System",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class RevenueSnapshot(BaseModel):
    system_id: str
    current_revenue: float
    mrr: float = None
    arr: float = None
    growth_rate: float = None
    active_customers: int = None

class DatabaseManager:
    def __init__(self):
        self.pool = None
    
    async def connect(self):
        """Establish database connection pool"""
        self.pool = await asyncpg.create_pool(
            host=os.getenv('DB_HOST', 'localhost'),
            port=int(os.getenv('DB_PORT', 5432)),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD'),
            database=os.getenv('DB_NAME', 'revenue_aggregator'),
            min_size=5,
            max_size=20
        )
        logger.info("Database connection pool established")
    
    async def close(self):
        """Close database connections"""
        if self.pool:
            await self.pool.close()
            logger.info("Database connections closed")
    
    async def get_all_systems(self) -> List[Dict]:
        """Fetch all active systems"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM systems WHERE status = 'active'"
            )
            return [dict(row) for row in rows]
    
    async def save_snapshot(self, snapshot: RevenueSnapshot):
        """Save revenue snapshot to database"""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO revenue_snapshots 
                (system_id, current_revenue, mrr, arr, growth_rate, active_customers)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                snapshot.system_id, snapshot.current_revenue,
                snapshot.mrr, snapshot.arr, snapshot.growth_rate,
                snapshot.active_customers
            )

db = DatabaseManager()

class RevenueAggregator:
    def __init__(self):
        self.session = None
    
    async def initialize(self):
        """Initialize HTTP session"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30)
        )
    
    async def fetch_system_revenue(self, system: Dict) -> Dict:
        """Fetch revenue from a single system"""
        try:
            async with self.session.get(
                f"{system['url']}{system['revenue_endpoint']}"
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"Fetched revenue for {system['name']}: {data}")
                    return {
                        'system_id': system['id'],
                        'data': data,
                        'success': True
                    }
                else:
                    logger.warning(f"Failed to fetch {system['name']}: {response.status}")
                    return {'system_id': system['id'], 'success': False}
        except Exception as e:
            logger.error(f"Error fetching {system['name']}: {e}")
            return {'system_id': system['id'], 'success': False}
    
    async def aggregate_all(self) -> Dict:
        """Aggregate revenue from all systems"""
        systems = await db.get_all_systems()
        tasks = [self.fetch_system_revenue(sys) for sys in systems]
        results = await asyncio.gather(*tasks)
        
        total_revenue = 0
        total_mrr = 0
        successful = 0
        
        for result in results:
            if result['success']:
                data = result['data']
                revenue = data.get('current_revenue', 0)
                total_revenue += revenue
                total_mrr += data.get('mrr', 0)
                successful += 1
                
                # Save snapshot
                snapshot = RevenueSnapshot(
                    system_id=result['system_id'],
                    current_revenue=revenue,
                    mrr=data.get('mrr'),
                    arr=data.get('arr'),
                    growth_rate=data.get('growth_rate'),
                    active_customers=data.get('active_customers')
                )
                await db.save_snapshot(snapshot)
        
        return {
            'total_revenue': total_revenue,
            'total_mrr': total_mrr,
            'total_arr': total_mrr * 12,
            'systems_reporting': successful,
            'total_systems': len(systems),
            'timestamp': datetime.utcnow().isoformat()
        }

aggregator = RevenueAggregator()

@app.on_event("startup")
async def startup():
    """Application startup"""
    await db.connect()
    await aggregator.initialize()
    logger.info("Revenue Aggregator started successfully")

@app.on_event("shutdown")
async def shutdown():
    """Application shutdown"""
    await db.close()
    if aggregator.session:
        await aggregator.session.close()
    logger.info("Revenue Aggregator shutdown complete")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "revenue-aggregator",
        "version": "1.0.0"
    }

@app.get("/ready")
async def readiness_check():
    """Readiness check endpoint"""
    if db.pool is None:
        raise HTTPException(status_code=503, detail="Database not ready")
    return {"status": "ready"}

@app.get("/revenue/current")
async def get_current_revenue():
    """Get current aggregated revenue"""
    return await aggregator.aggregate_all()

@app.get("/revenue/history")
async def get_revenue_history(days: int = 30):
    """Get revenue history"""
    async with db.pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT 
                DATE(snapshot_timestamp) as date,
                SUM(current_revenue) as total_revenue
            FROM revenue_snapshots
            WHERE snapshot_timestamp >= NOW() - INTERVAL '$1 days'
            GROUP BY DATE(snapshot_timestamp)
            ORDER BY date DESC
            """,
            days
        )
        return [dict(row) for row in rows]

@app.get("/systems")
async def list_systems():
    """List all systems"""
    return await db.get_all_systems()

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8080,
        log_level="info"
    )
