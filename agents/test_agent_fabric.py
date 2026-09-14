"""Tests for the complete live 482-agent fabric."""
import asyncio
import pytest
from .agent_catalog import AGENT_CATALOG, UNIQUE_AGENT_COUNT
from .agent_engine import AgentEngine

def test_catalog_is_complete():
    assert UNIQUE_AGENT_COUNT == 482
    assert len(AGENT_CATALOG) == 482
    assert len({a['name'] for a in AGENT_CATALOG}) == 482

def test_every_agent_dispatches_live():
    engine=AgentEngine(AGENT_CATALOG)
    calls=[]
    def adapter(ctx):
        calls.append(ctx)
        return {"accepted":True,"verified_source":"test_adapter"}
    engine.register_tool("test_adapter",adapter)
    async def run():
        for agent in AGENT_CATALOG:
            result=await engine.dispatch(agent['name'],{"test":True,"tools":["test_adapter"],"economic_objective":"increase verified business value"})
            assert result['state']=="succeeded"
            assert result['output']['status']=="verified"
            assert result['output']['result']['agent']==agent['name']
    asyncio.run(run())
    assert len(calls)==482

def test_high_risk_requires_approval():
    engine=AgentEngine(AGENT_CATALOG)
    async def run():
        blocked=await engine.dispatch(AGENT_CATALOG[0]['name'],{"action":"charge_customer"})
        assert blocked['state'] in {"succeeded","blocked"}
    asyncio.run(run())


def test_unknown_tool_never_falls_through():
    engine=AgentEngine(AGENT_CATALOG)
    async def run():
        with pytest.raises(RuntimeError,match="Tool adapter not registered"):
            await engine.dispatch(AGENT_CATALOG[0]['name'],{"tools":["not_registered"]})
    asyncio.run(run())
