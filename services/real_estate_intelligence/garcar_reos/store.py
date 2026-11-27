"""SQLite casebook with transactional, tamper-evident audit trail.

The hash chain detects accidental/unauthorized DB alteration but does not prevent
DB administrators from rewriting history. External anchoring is not implemented.
"""
from __future__ import annotations
import hashlib
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from .models import BuyerIn, EvidenceIn, PropertyIn, DecisionIn, UnderwritingIn
from .underwriting import analyze

REQUIRED_REVIEW_EVIDENCE = {"asking_price", "arv", "repairs", "ownership"}

def stamp() -> str:
    return datetime.now(timezone.utc).isoformat()

def dump(value: Any) -> str:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)

class MissingCase(KeyError):
    pass

class Conflict(ValueError):
    pass

class CaseStore:
    def __init__(self, path: str | Path):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connection(self, write: bool = False):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=15000")
        try:
            if write:
                db.execute("BEGIN IMMEDIATE")
            yield db
            if write:
                db.commit()
        except Exception:
            if write:
                db.rollback()
            raise
        finally:
            db.close()

    def initialize(self):
        with self.connection() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS cases (
                  id TEXT PRIMARY KEY, address_key TEXT UNIQUE NOT NULL,
                  payload TEXT NOT NULL, review_status TEXT NOT NULL,
                  created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS evidence (
                  id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(id),
                  payload TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS underwriting (
                  id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(id),
                  assumptions TEXT NOT NULL, result TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS buyers (
                  id TEXT PRIMARY KEY, payload TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS decisions (
                  id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(id),
                  payload TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audit (
                  seq INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL,
                  action TEXT NOT NULL, subject_id TEXT NOT NULL, payload_hash TEXT NOT NULL,
                  prev_hash TEXT NOT NULL, event_hash TEXT NOT NULL
                );
            """)

    @staticmethod
    def _audit(db: sqlite3.Connection, action: str, subject: str, payload: Any) -> None:
        last = db.execute("SELECT event_hash FROM audit ORDER BY seq DESC LIMIT 1").fetchone()
        prev = last[0] if last else "0" * 64
        at = stamp()
        payload_hash = hashlib.sha256(dump(payload).encode("utf-8")).hexdigest()
        event = dump([at, action, subject, payload_hash, prev])
        event_hash = hashlib.sha256(event.encode("utf-8")).hexdigest()
        db.execute("INSERT INTO audit(at,action,subject_id,payload_hash,prev_hash,event_hash) VALUES(?,?,?,?,?,?)",
                   (at, action, subject, payload_hash, prev, event_hash))

    def verify_audit(self) -> dict[str, Any]:
        previous = "0" * 64
        with self.connection() as db:
            for item in db.execute("SELECT * FROM audit ORDER BY seq"):
                if item["prev_hash"] != previous:
                    return {"valid": False, "bad_seq": item["seq"]}
                expected = hashlib.sha256(dump([item["at"], item["action"], item["subject_id"],
                                                item["payload_hash"], previous]).encode()).hexdigest()
                if expected != item["event_hash"]:
                    return {"valid": False, "bad_seq": item["seq"]}
                previous = item["event_hash"]
            count = db.execute("SELECT COUNT(*) FROM audit").fetchone()[0]
        return {"valid": True, "events": count, "last_hash": previous,
                "warning": "Hash chain is not independently anchored; DB admins can rewrite history."}

    def add_case(self, request: PropertyIn) -> dict[str, Any]:
        p = request.model_dump(mode="json")
        key = "|".join(str(p[k]).strip().lower() for k in ("street_address", "city", "state", "postal_code"))
        uid = str(uuid.uuid4())
        now = stamp()
        with self.connection(True) as db:
            try:
                db.execute("INSERT INTO cases VALUES(?,?,?,?,?,?)", (uid, key, dump(p), "draft", now, now))
            except sqlite3.IntegrityError as e:
                raise Conflict("A case already exists for this address") from e
            self._audit(db, "case.created", uid, p)
        return {"id": uid, **p, "review_status": "draft", "created_at": now}

    def get_case(self, uid: str) -> dict[str, Any]:
        with self.connection() as db:
            row = db.execute("SELECT * FROM cases WHERE id=?", (uid,)).fetchone()
        if not row:
            raise MissingCase(uid)
        return {"id": uid, **json.loads(row["payload"]), "review_status": row["review_status"],
                "created_at": row["created_at"], "updated_at": row["updated_at"]}

    def list_cases(self, limit: int = 50) -> list[dict[str, Any]]:
        with self.connection() as db:
            ids = [row["id"] for row in db.execute("SELECT id FROM cases ORDER BY created_at DESC,id DESC LIMIT ?", (limit,))]
        return [self.get_case(uid) for uid in ids]

    def add_evidence(self, uid: str, request: EvidenceIn) -> dict[str, Any]:
        self.get_case(uid)
        pid = str(uuid.uuid4())
        p = request.model_dump(mode="json")
        now = stamp()
        with self.connection(True) as db:
            db.execute("INSERT INTO evidence VALUES(?,?,?,?)", (pid, uid, dump(p), now))
            self._audit(db, "evidence.added", uid, {"evidence_id": pid, **p})
        return {"id": pid, "case_id": uid, **p, "created_at": now}

    def list_evidence(self, uid: str) -> list[dict[str, Any]]:
        self.get_case(uid)
        with self.connection() as db:
            rows = db.execute("SELECT * FROM evidence WHERE case_id=? ORDER BY created_at DESC,id DESC", (uid,)).fetchall()
        return [{"id": r["id"], "case_id": uid, **json.loads(r["payload"]), "created_at": r["created_at"]} for r in rows]

    def run_underwriting(self, uid: str, request: UnderwritingIn) -> dict[str, Any]:
        case = self.get_case(uid)
        result = analyze(Decimal(case["asking_price"]), request)
        record = {"id": str(uuid.uuid4()), "case_id": uid,
                  "assumptions": request.model_dump(mode="json"), "result": result.model_dump(mode="json"),
                  "created_at": stamp()}
        with self.connection(True) as db:
            db.execute("INSERT INTO underwriting VALUES(?,?,?,?,?)",
                       (record["id"], uid, dump(record["assumptions"]), dump(record["result"]), record["created_at"]))
            self._audit(db, "underwriting.created", uid, record)
        return record

    def latest_underwriting(self, uid: str) -> dict[str, Any] | None:
        self.get_case(uid)
        with self.connection() as db:
            row = db.execute("SELECT * FROM underwriting WHERE case_id=? ORDER BY created_at DESC,rowid DESC LIMIT 1", (uid,)).fetchone()
        return ({"id": row["id"], "case_id": uid, "assumptions": json.loads(row["assumptions"]),
                 "result": json.loads(row["result"]), "created_at": row["created_at"]} if row else None)

    def readiness(self, uid: str) -> dict[str, Any]:
        evidence = self.list_evidence(uid)
        seen = set()
        stale = []
        now = datetime.now(timezone.utc)
        for e in evidence:
            age = now - datetime.fromisoformat(e["observed_at"])
            if e.get("reviewed_by") and age <= timedelta(days=90):
                seen.add(e["field"])
            elif e["field"] in REQUIRED_REVIEW_EVIDENCE:
                stale.append(e["field"])
        missing = sorted(REQUIRED_REVIEW_EVIDENCE - seen)
        underwritten = self.latest_underwriting(uid) is not None
        return {"ready_for_research_approval": not missing and underwritten,
                "missing_current_operator_reviewed_evidence": missing,
                "has_underwriting": underwritten,
                "important": "Operator annotations are not external verification; title, legal and compliance checks remain mandatory before transactions."}

    def decide(self, uid: str, request: DecisionIn) -> dict[str, Any]:
        self.get_case(uid)
        readiness = self.readiness(uid)
        if request.decision == "approve_research" and not readiness["ready_for_research_approval"]:
            raise Conflict("Research approval blocked: missing current reviewed evidence or underwriting")
        record = {"id": str(uuid.uuid4()), "case_id": uid, **request.model_dump(mode="json"), "created_at": stamp()}
        status = "research_approved" if request.decision == "approve_research" else "research_rejected"
        with self.connection(True) as db:
            db.execute("INSERT INTO decisions VALUES(?,?,?,?)", (record["id"], uid, dump(record), record["created_at"]))
            db.execute("UPDATE cases SET review_status=?, updated_at=? WHERE id=?", (status, record["created_at"], uid))
            self._audit(db, "case.research_decision", uid, record)
        return {**record, "review_status": status, "warning": "No contract, offer, outreach or disbursement has been authorized or performed."}

    def add_buyer(self, request: BuyerIn) -> dict[str, Any]:
        record = {"id": str(uuid.uuid4()), **request.model_dump(mode="json"), "created_at": stamp()}
        with self.connection(True) as db:
            db.execute("INSERT INTO buyers VALUES(?,?,?)", (record["id"], dump(record), record["created_at"]))
            self._audit(db, "buyer.criteria_added", record["id"], record)
        return record

    def match_buyers(self, uid: str) -> list[dict[str, Any]]:
        case = self.get_case(uid)
        with self.connection() as db:
            buyers = [json.loads(row[0]) for row in db.execute("SELECT payload FROM buyers")]
        matches = []
        for b in buyers:
            if (b["status"] == "criteria_reviewed"
                and case["county"].casefold() in {c.casefold() for c in b["counties"]}
                and case["property_type"] in b["property_types"]
                and Decimal(case["asking_price"]) <= Decimal(b["max_acquisition_price"])):
                matches.append({"buyer_id": b["id"], "label": b["label"],
                                "criteria_source_url": b["criteria_source_url"],
                                "match_type": "preliminary_criteria_only",
                                "warning": "Not proof of cash, a committed buyer, or permission to contact."})
        return matches
