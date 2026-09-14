"""Smoke tests for the complete 482-agent fabric."""
import asyncio
from .agent_catalog import AGENT_CATALOG, UNIQUE_AGENT_COUNT
from .agent_engine import AgentEngine

def test_catalog_is_complete():
    assert UNIQUE_AGENT_COUNT == 482
    assert len(AGENT_CATALOG) == 482
    assert len({a['name'] for a in AGENT_CATALOG}) == 482

def test_every_agent_dispatches():
    engine = AgentEngine(AGENT_CATALOG)
    async def run():
        for agent in AGENT_CATALOG:
            result = await engine.dispatch(agent['name'], {'test': True}, dry_run=True)
            assert result['state'] == 'succeeded'
            assert result['output']['result']['agent'] == agent['name']
    asyncio.run(run())
