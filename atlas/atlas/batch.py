"""Johnson County / South DFW shop pack. Draft only. No send."""
from __future__ import annotations
from .main import run
from .schemas import ShopIntake

SEED = [
    ShopIntake(shop="Cleburne Comfort HVAC", trade="HVAC", city="Cleburne", owner="Mike", ticket=4500, jobs_week=8),
    ShopIntake(shop="Grandview Drain & Pipe", trade="Plumbing", city="Grandview", owner="Dale", ticket=2800, jobs_week=10),
    ShopIntake(shop="Alvarado Amp Electric", trade="Electrical", city="Alvarado", owner="Chris", ticket=2200, jobs_week=9),
    ShopIntake(shop="Burleson Roof & Ridge", trade="Roofing", city="Burleson", owner="Pat", ticket=12000, jobs_week=4),
    ShopIntake(shop="Midlothian Mechanical", trade="HVAC", city="Midlothian", owner="Sam", ticket=5200, jobs_week=7),
]

def run_seed() -> list[dict]:
    return [run(shop) for shop in SEED]

if __name__ == "__main__":
    for p in run_seed():
        print(p["outreach_sms"][:80], "| leak", p["monthly_leak_total"])
