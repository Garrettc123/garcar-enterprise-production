"""Explicit adapters from governed agent missions to the live revenue engine.

Adapters are the only place where agent intent becomes a business side effect.
They return source-system results; the fabric must not manufacture revenue.
"""
from __future__ import annotations
from typing import Any
from .revenue_engine import RevenueEngine

class RevenueAdapters:
    def __init__(self, engine: RevenueEngine):
        self.engine=engine

    def hunt_capture(self, ctx:dict[str,Any])->dict[str,Any]:
        return self.engine.hunt_and_capture(source=str(ctx.get("source","super_fabric")),email=ctx.get("email"))

    def advance_pipeline(self, ctx:dict[str,Any])->dict[str,Any]:
        prospect_id=ctx.get("prospect_id")
        if not prospect_id: return {"status":"blocked","reason":"prospect_id required"}
        return self.engine.advance_pipeline(str(prospect_id),str(ctx.get("target","trust")))

    def create_checkout_opportunity(self, ctx:dict[str,Any])->dict[str,Any]:
        email=ctx.get("email")
        if not email: return {"status":"blocked","reason":"real customer email required"}
        return self.engine.force_conversion_opportunity(str(email),str(ctx.get("plan","starter")),ctx.get("lead_id"))

    def churn_scan(self, ctx:dict[str,Any])->dict[str,Any]:
        return self.engine.run_churn_scan()

    def close_and_amplify(self, ctx:dict[str,Any])->dict[str,Any]:
        customer_id=ctx.get("customer_id")
        if not customer_id: return {"status":"blocked","reason":"customer_id required"}
        return self.engine.close_and_amplify(str(customer_id),float(ctx.get("roi",3.0)))

    def registry(self)->dict[str,Any]:
        return {"hunt_capture":self.hunt_capture,"advance_pipeline":self.advance_pipeline,
                "create_checkout_opportunity":self.create_checkout_opportunity,
                "churn_scan":self.churn_scan,"close_and_amplify":self.close_and_amplify}
