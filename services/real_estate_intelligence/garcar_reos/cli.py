"""Local evidence-first CSV ingestion. No network calls or messaging."""
from __future__ import annotations
import argparse
import csv
import json
import os
from pathlib import Path
from pydantic import ValidationError
from .models import PropertyIn
from .store import CaseStore, Conflict

REQUIRED = {"street_address", "city", "state", "postal_code", "county", "property_type",
            "asking_price", "source_url", "observed_at"}
ALLOWED = REQUIRED | {"operator_notes"}

def import_csv(path: str, db_path: str, max_rows: int = 500) -> dict:
    p = Path(path)
    if not p.is_file() or p.stat().st_size > 2_000_000:
        raise ValueError("CSV must exist and be at most 2 MB")
    if not 1 <= max_rows <= 500:
        raise ValueError("max_rows must be in 1..500")
    s = CaseStore(db_path)
    result = {"imported": 0, "duplicates": 0, "invalid": []}
    with p.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []
        if len(fields) != len(set(fields)) or not REQUIRED.issubset(fields) or set(fields) - ALLOWED:
            raise ValueError("CSV headers missing, duplicated, or contain prohibited columns")
        for i, row in enumerate(reader, 2):
            if i > max_rows + 1:
                raise ValueError("CSV row limit exceeded")
            try:
                request = PropertyIn.model_validate({key: value for key, value in row.items() if key in ALLOWED})
                s.add_case(request)
                result["imported"] += 1
            except Conflict:
                result["duplicates"] += 1
            except (ValidationError, ValueError) as e:
                result["invalid"].append({"row": i, "reason": str(e)[:250]})
    return result

def main():
    p = argparse.ArgumentParser(prog="reos", description="Garcar Real Estate Intelligence OS")
    p.add_argument("--db", default=os.getenv("REOS_DB_PATH", "./reos.db"))
    sub = p.add_subparsers(dest="command", required=True)
    ip = sub.add_parser("import-csv")
    ip.add_argument("path")
    ip.add_argument("--max-rows", type=int, default=500)
    sub.add_parser("verify-audit")
    sub.add_parser("list-cases")
    args = p.parse_args()
    if args.command == "import-csv":
        print(json.dumps(import_csv(args.path, args.db, args.max_rows), indent=2))
    elif args.command == "verify-audit":
        print(json.dumps(CaseStore(args.db).verify_audit(), indent=2))
    else:
        print(json.dumps(CaseStore(args.db).list_cases(), indent=2))

if __name__ == "__main__":
    main()
