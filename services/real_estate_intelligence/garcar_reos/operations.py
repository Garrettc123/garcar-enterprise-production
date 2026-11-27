"""Local operations plane: human-controlled research, pipeline, tasks, and drafts.

No function in this module contacts third parties, signs a document, or handles funds.
"""
from __future__ import annotations
import json
import sqlite3
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Literal
from pydantic import Field, HttpUrl, field_validator
from .models import StrictModel, PropertyIn
from .store import CaseStore, Conflict, MissingCase, stamp, dump

PHASES = ("intake", "research", "qualified", "diligence", "offer_review", "under_contract", "closed", "disqualified")
TRANSITIONS = {
    "intake": {"research", "disqualified"},
    "research": {"qualified", "disqualified"},
    "qualified": {"diligence", "disqualified"},
    "diligence": {"offer_review", "disqualified"},
    "offer_review": {"diligence", "under_contract", "disqualified"},
    "under_contract": {"closed", "disqualified"},
    "closed": set(), "disqualified": set(),
}
REQUIRED_DILIGENCE = ("ownership", "title", "liens", "property_taxes", "zoning", "comps", "repairs", "funding", "equitable_interest_disclosure", "legal_review")
HIGH_RISK = {"offer_review", "under_contract", "closed"}

class PhaseChange(StrictModel):
    target: Literal["intake", "research", "qualified", "diligence", "offer_review", "under_contract", "closed", "disqualified"]
    actor: str = Field(min_length=2, max_length=120)
    rationale: str = Field(min_length=12, max_length=1500)
    external_record_url: HttpUrl | None = None

class ChecklistUpdate(StrictModel):
    key: Literal["ownership", "title", "liens", "property_taxes", "zoning", "comps", "repairs", "funding", "equitable_interest_disclosure", "legal_review"]
    status: Literal["passed", "blocked", "not_checked"]
    evidence_url: HttpUrl | None = None
    reviewed_by: str = Field(min_length=2, max_length=120)
    note: str = Field(min_length=12, max_length=2000)

class TaskIn(StrictModel):
    title: str = Field(min_length=4, max_length=200)
    description: str = Field(default="", max_length=1000)
    assigned_to: str = Field(min_length=2, max_length=120)
    due_at: datetime
    priority: Literal["low", "normal", "high", "critical"] = "normal"
    source_url: HttpUrl | None = None

    @field_validator("due_at")
    @classmethod
    def aware(cls, v: datetime) -> datetime:
        if not v.tzinfo or v.utcoffset() is None:
            raise ValueError("due_at needs a timezone offset")
        return v

class TaskUpdate(StrictModel):
    status: Literal["open", "in_progress", "done", "blocked"]
    actor: str = Field(min_length=2, max_length=120)
    note: str = Field(default="", max_length=1000)

class AgentProposal(StrictModel):
    agent_id: str = Field(min_length=3, max_length=120)
    property: PropertyIn
    research_rationale: str = Field(min_length=16, max_length=2000)
    # A URL is evidence provenance, not proof the URL is live or the information accurate.

class DraftIn(StrictModel):
    audience: Literal["seller", "buyer", "title_company", "investor", "internal"]
    channel: Literal["email", "call_script", "internal_memo"]
    subject: str = Field(min_length=3, max_length=200)
    content: str = Field(min_length=15, max_length=4000)
    prepared_by: str = Field(min_length=2, max_length=120)
    # No recipient address and no send endpoint on purpose.

class ProposalDecision(StrictModel):
    decision: Literal["accept", "reject"]
    reviewer: str = Field(min_length=2, max_length=120)
    rationale: str = Field(min_length=12, max_length=1200)

class OperationsStore(CaseStore):
    def initialize(self):
        super().initialize()
        with self.connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS case_phases (
                    case_id TEXT PRIMARY KEY REFERENCES cases(id), phase TEXT NOT NULL,
                    changed_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS checklist (
                    case_id TEXT NOT NULL REFERENCES cases(id), item_key TEXT NOT NULL,
                    payload TEXT NOT NULL, changed_at TEXT NOT NULL,
                    PRIMARY KEY(case_id, item_key)
                );
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(id),
                    payload TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS agent_proposals (
                    id TEXT PRIMARY KEY, payload TEXT NOT NULL, status TEXT NOT NULL,
                    case_id TEXT, created_at TEXT NOT NULL, resolved_at TEXT
                );
                CREATE TABLE IF NOT EXISTS drafts (
                    id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(id),
                    payload TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_tasks_due ON tasks(status, updated_at);
            """)

    def phase(self, case_id: str) -> dict[str, Any]:
        self.get_case(case_id)
        with self.connection() as db:
            r = db.execute("SELECT phase,changed_at FROM case_phases WHERE case_id=?", (case_id,)).fetchone()
        return {"case_id": case_id, "phase": r["phase"] if r else "intake",
                "changed_at": r["changed_at"] if r else None,
                "allowed_next": sorted(TRANSITIONS[r["phase"] if r else "intake"])}

    def get_checklist(self, case_id: str) -> dict[str, Any]:
        self.get_case(case_id)
        with self.connection() as db:
            rows = db.execute("SELECT item_key,payload,changed_at FROM checklist WHERE case_id=?", (case_id,)).fetchall()
        found = {r["item_key"]: {**json.loads(r["payload"]), "changed_at": r["changed_at"]} for r in rows}
        now = datetime.now(timezone.utc)
        items = []
        for key in REQUIRED_DILIGENCE:
            row = found.get(key)
            fresh = (bool(row) and row["status"] == "passed" and bool(row.get("evidence_url"))
                     and now - datetime.fromisoformat(row["changed_at"]) <= timedelta(days=90))
            items.append({"key": key, "status": row["status"] if row else "not_checked",
                          "fresh_pass": fresh, "details": row})
        return {"case_id": case_id, "complete": all(x["fresh_pass"] for x in items),
                "items": items, "warning": "Operator attestations are not title opinions, appraisals or legal sign-off."}

    def update_check(self, case_id: str, data: ChecklistUpdate) -> dict[str, Any]:
        self.get_case(case_id)
        if data.status == "passed" and data.evidence_url is None:
            raise Conflict("Passing a check requires a source URL")
        p = data.model_dump(mode="json")
        now = stamp()
        with self.connection(True) as db:
            db.execute("INSERT INTO checklist(case_id,item_key,payload,changed_at) VALUES(?,?,?,?) "
                       "ON CONFLICT(case_id,item_key) DO UPDATE SET payload=excluded.payload, changed_at=excluded.changed_at",
                       (case_id, data.key, dump(p), now))
            self._audit(db, "checklist.updated", case_id, {**p, "changed_at": now})
        return {"case_id": case_id, **p, "changed_at": now}

    def change_phase(self, case_id: str, change: PhaseChange, approved: bool = False) -> dict[str, Any]:
        current = self.phase(case_id)["phase"]
        if change.target not in TRANSITIONS[current]:
            raise Conflict(f"Disallowed transition: {current} -> {change.target}")
        if change.target in HIGH_RISK and not approved:
            raise Conflict("Separate human approver credential required for this stage")
        if change.target == "qualified" and self.get_case(case_id)["review_status"] != "research_approved":
            raise Conflict("Research must be explicitly approved before qualification")
        if change.target == "offer_review" and not self.get_checklist(case_id)["complete"]:
            raise Conflict("Diligence checklist incomplete or stale")
        if change.target in {"under_contract", "closed"} and not change.external_record_url:
            raise Conflict("External executed contract or closing record URL required; app cannot execute it")
        now = stamp()
        with self.connection(True) as db:
            # Check phase again within write transaction to guard concurrent transitions.
            r = db.execute("SELECT phase FROM case_phases WHERE case_id=?", (case_id,)).fetchone()
            if (r[0] if r else "intake") != current:
                raise Conflict("Phase changed concurrently; refresh and retry")
            db.execute("INSERT INTO case_phases(case_id,phase,changed_at) VALUES(?,?,?) "
                       "ON CONFLICT(case_id) DO UPDATE SET phase=excluded.phase,changed_at=excluded.changed_at",
                       (case_id, change.target, now))
            self._audit(db, "phase.changed", case_id, {**change.model_dump(mode="json"), "from": current})
        return {"case_id": case_id, "from": current, "phase": change.target, "changed_at": now,
                "notice": "Tracking only; no contact, offer, signature or payment took place."}

    def add_task(self, case_id: str, request: TaskIn) -> dict[str, Any]:
        self.get_case(case_id)
        record = {"id": str(uuid.uuid4()), "case_id": case_id, **request.model_dump(mode="json"),
                  "status": "open", "created_at": stamp(), "updated_at": stamp()}
        with self.connection(True) as db:
            db.execute("INSERT INTO tasks VALUES(?,?,?,?,?,?)",
                       (record["id"], case_id, dump(request), "open", record["created_at"], record["updated_at"]))
            self._audit(db, "task.created", case_id, record)
        return record

    def list_tasks(self, case_id: str | None = None, due_only: bool = False, limit: int = 100) -> list[dict[str, Any]]:
        if case_id: self.get_case(case_id)
        with self.connection() as db:
            rows = db.execute("SELECT * FROM tasks ORDER BY created_at DESC,id DESC LIMIT 1000").fetchall()
        tasks = [{"id": r["id"], "case_id": r["case_id"], **json.loads(r["payload"]),
                  "status": r["status"], "created_at": r["created_at"], "updated_at": r["updated_at"]}
                 for r in rows]
        if case_id: tasks = [t for t in tasks if t["case_id"] == case_id]
        if due_only: tasks = [t for t in tasks if t["status"] != "done" and datetime.fromisoformat(t["due_at"]) <= datetime.now(timezone.utc)]
        return tasks[:limit]

    def update_task(self, task_id: str, request: TaskUpdate) -> dict[str, Any]:
        now = stamp()
        with self.connection(True) as db:
            row = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
            if not row: raise MissingCase(task_id)
            db.execute("UPDATE tasks SET status=?,updated_at=? WHERE id=?", (request.status, now, task_id))
            self._audit(db, "task.status_changed", row["case_id"], {"task_id": task_id, **request.model_dump(mode="json")})
        return {"id": task_id, "case_id": row["case_id"], "status": request.status, "updated_at": now}

    def submit_proposal(self, proposal: AgentProposal) -> dict[str, Any]:
        rid, now = str(uuid.uuid4()), stamp()
        p = proposal.model_dump(mode="json")
        with self.connection(True) as db:
            db.execute("INSERT INTO agent_proposals VALUES(?,?,?,?,?,?)", (rid, dump(p), "pending", None, now, None))
            self._audit(db, "agent.proposal_submitted", rid, p)
        return {"id": rid, "status": "pending", "created_at": now, **p}

    def list_proposals(self, status: str | None = None) -> list[dict[str, Any]]:
        with self.connection() as db:
            rows = db.execute("SELECT * FROM agent_proposals ORDER BY created_at DESC,id DESC LIMIT 200").fetchall()
        return [{"id": r["id"], **json.loads(r["payload"]), "status": r["status"],
                 "case_id": r["case_id"], "created_at": r["created_at"]}
                for r in rows if status is None or r["status"] == status]

    def resolve_proposal(self, pid: str, decision: ProposalDecision) -> dict[str, Any]:
        # Single SQLite write transaction makes acceptance idempotent under concurrency.
        now = stamp()
        with self.connection(True) as db:
            row = db.execute("SELECT * FROM agent_proposals WHERE id=?", (pid,)).fetchone()
            if not row: raise MissingCase(pid)
            if row["status"] != "pending": raise Conflict("Proposal already resolved")
            cid = None
            if decision.decision == "accept":
                source = json.loads(row["payload"])["property"]
                key = "|".join(str(source[k]).strip().lower() for k in ("street_address", "city", "state", "postal_code"))
                cid = str(uuid.uuid4())
                try:
                    db.execute("INSERT INTO cases VALUES(?,?,?,?,?,?)", (cid, key, dump(source), "draft", now, now))
                except sqlite3.IntegrityError as e:
                    raise Conflict("Property already exists; resolve existing case before importing") from e
                self._audit(db, "case.created_via_agent_review", cid, source)
            db.execute("UPDATE agent_proposals SET status=?, case_id=?, resolved_at=? WHERE id=?",
                       ("accepted" if cid else "rejected", cid, now, pid))
            self._audit(db, "agent.proposal_resolved", pid, {"decision": decision.model_dump(mode="json"), "case_id": cid})
        return {"id": pid, "status": "accepted" if cid else "rejected", "case_id": cid,
                "resolved_at": now, "notice": "Accepted research intake only; no transaction authority."}

    def create_draft(self, cid: str, draft: DraftIn) -> dict[str, Any]:
        self.get_case(cid)
        rid, now = str(uuid.uuid4()), stamp()
        p = draft.model_dump(mode="json")
        with self.connection(True) as db:
            db.execute("INSERT INTO drafts VALUES(?,?,?,?)", (rid, cid, dump(p), now))
            self._audit(db, "communication.draft_created", cid, {"id": rid, **p})
        return {"id": rid, "case_id": cid, "status": "unsent_draft", "created_at": now, **p}

    def list_drafts(self, cid: str) -> list[dict[str, Any]]:
        self.get_case(cid)
        with self.connection() as db:
            rows = db.execute("SELECT * FROM drafts WHERE case_id=? ORDER BY created_at DESC,id DESC", (cid,)).fetchall()
        return [{"id": r["id"], "case_id": cid, **json.loads(r["payload"]),
                 "created_at": r["created_at"], "status": "unsent_draft"} for r in rows]

    def dossier(self, cid: str) -> dict[str, Any]:
        return {"case": self.get_case(cid), "phase": self.phase(cid), "readiness": self.readiness(cid),
                "checklist": self.get_checklist(cid), "underwriting": self.latest_underwriting(cid),
                "evidence": self.list_evidence(cid), "tasks": self.list_tasks(cid),
                "buyer_matches": self.match_buyers(cid), "drafts": self.list_drafts(cid),
                "execution_enabled": False, "not_authorized": ["outbound_messaging", "contract_execution", "payments", "offers"]}

    def metrics(self) -> dict[str, Any]:
        with self.connection() as db:
            cases = db.execute("SELECT id, review_status FROM cases").fetchall()
            stages = {r["case_id"]: r["phase"] for r in db.execute("SELECT case_id,phase FROM case_phases")}
            count_tasks = db.execute("SELECT status, COUNT(*) count FROM tasks GROUP BY status").fetchall()
            proposals = db.execute("SELECT status, COUNT(*) count FROM agent_proposals GROUP BY status").fetchall()
        phase_counts = {s: 0 for s in PHASES}
        for c in cases: phase_counts[stages.get(c["id"], "intake")] += 1
        return {"case_count": len(cases), "phases": phase_counts,
                "research_approved": sum(c["review_status"] == "research_approved" for c in cases),
                "tasks": {r["status"]: r["count"] for r in count_tasks},
                "agent_proposals": {r["status"]: r["count"] for r in proposals},
                "verified_live_revenue_usd": None,
                "notice": "Revenue and investment returns are not verified by this service."}
