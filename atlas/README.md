# ATLAS — CrewAI multi-agent revenue workflow

Sequential crew: Intake Scout → Leak Analyst → Fulfillment Writer → Closer.
Dry-run default. Human gate on send. Live SKUs wired.

```bash
cd atlas
pip install -r requirements.txt
python -m atlas.main --shop "Cleburne Comfort HVAC" --trade HVAC --city Cleburne --owner Mike
```
