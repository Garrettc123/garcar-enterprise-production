# Garcar Enterprise: SOC 2 readiness and evidence register

**Assessment date:** 2026-11-25 (America/Chicago)  
**Assessment type:** limited connector-based technical review, not an independent audit  
**Claim status:** **NOT AUDITED / SOC 2 COMPLIANCE NOT VERIFIED**

SOC 2 is an independent CPA attestation under the AICPA Trust Services Criteria. No audit opinion, qualified scope, operating-period evidence, or management assertion was verified during this review. Never label the company `SOC 2 compliant`, `SOC 2 certified`, or `SOC 2 Type II audited` until a qualified CPA auditor issues the applicable report.

## Proposed scope

Security Trust Services Criteria (common criteria) first. Evaluate Availability and Confidentiality due to potential service uptime and customer-data obligations; add Processing Integrity and Privacy if service commitments and personal-information processing require them. Agree final scope with management and auditor.

System boundary must be inventoried across the real deployed Garcar services, including: payment/webhook processing; lead-review CSV ingestion/delivery; API services; AI agents and operator controls; production databases/backups; GitHub CI/CD; and actual Railway, Cloudflare, Supabase, Render/Vercel, Stripe and other subprocessors in use. **Do not assume that a planned service is deployed or that a vendor's own SOC 2 report covers Garcar's controls.**

## Evidence-based findings

| Area | Observed evidence | Status | Required action |
| --- | --- | --- | --- |
| Change/release | Main production repo has CI and CodeQL workflows and a CODEOWNERS file. Latest observed CI/CodeQL checks on main succeeded (2026-11-25 UTC). | Partial | Require review and passing checks with verified branch protection; retain change approvals and release records |
| Branch governance | No repository rulesets were returned for public production or payments repositories. The connected GitHub integration was denied access to the branch-protection endpoint (403). | Unknown | Admin must verify branch protection and environment reviewers; absence of rulesets does **not** prove absence of branch protection |
| Payment deployment | `garcar-payments/.github/workflows/deploy-payments.yml` printed deployment and endpoint success without executing deployment or endpoint verification. | Gap | Remove deceptive workflow; retain only actual gated deploy and independent health verification |
| Secret rotation | `garcar-payments/.github/workflows/keyless-secret-rotation.yml` generated a temporary signing key and modified webhook event subscriptions; that is not verified Stripe signing-secret rotation. | Gap | Remove misleading automation; build controlled rotation with dual-secret overlap and rollback |
| Backups | Payment backup workflow previously returned success if `DATABASE_URL` was unset; its optional check parsed a SQL header rather than restoring a database. | Gap | Fail closed, validate archived data; separately document isolated restore drill and RPO/RTO |
| Current workflow health | Payment repo had failing `garcar-pipeline`, `vault-secrets` and `stripe-smoke-test` runs on 2026-11-25 UTC. | Gap | Investigate actual logs and reconcile reasons, owners, and outcomes before accepting release evidence |
| Access/identity | MFA, SSO, least-privilege role assignments, service account inventory, and access recertification were not independently checked. | Unknown | Quarterly access reviews, offboarding checklists, protected production approvals |
| Vulnerability management | Workflows include dependency checks and CodeQL; organization-wide coverage, alert triage SLA, vulnerability exceptions, and ticket closure evidence were not established. | Partial | Centralize severity, assign remediation deadlines, prove scans run on all deployed repos |
| Data confidentiality | Actual production encryption, key scope, retention/deletion, customer-data isolation and log redaction not verified. | Unknown | Data flow diagram, secrets inventory, retention/deletion controls and tests |
| Availability/DR | Uptime objective, incident alerts, independent backups and full restore evidence not verified. | Unknown | Measure uptime, define RTO/RPO, run isolated restore test, prove backup notifications |
| Vendors and boundaries | Contractor/subprocessor list, SOC reports, DPAs and shared-responsibility evaluations not inspected. | Unknown | Vendor register, due diligence, report review and documented residual risk |
| Agent governance | Production tool grants, approval-gate enforcement, audit-chain integrity and kill-switch effectiveness not tested in this assessment. | Unknown | Test unauthorized actions are denied, privileged events are recorded, and emergency disable works |
| Privacy & personnel | Written privacy notice, onboarding, security training and incident exercise records not verified. | Unknown | Approve written policies, retain dated acknowledgments, test response process |

## Proposed control owners and evidence cadence

| Control | Owner | Frequency | Required proof |
| --- | --- | --- | --- |
| Identity / access review | Founder or delegated security owner | Quarterly and after offboarding | Exported access matrix, approvals, revoked identities |
| Pull request and release review | Engineering owner | Every production change | Reviewed PR, required checks, deployment event and independent health outcome |
| Vulnerability triage | Engineering owner | Weekly plus critical alerts | Scanner runs, exceptions, owner, fix commit, retest |
| Backup verification | Infrastructure owner | Daily backup checks, quarterly isolated restore | Actual archive ID, integrity result, independent recovery drill |
| Incident detection & response | Security owner | Continuous alerting; annual tabletop | Alert routing, incident ticket, timeline, lessons learned |
| Vendor assurance | Security owner | On onboarding and annually | Vendor register, assurance report, review sign-off |
| Agent privileged action controls | Engineering and security owner | Every privileged run; monthly sample | Request, approval, execution and immutable audit record |
| Data retention/deletion | Data owner | At termination/request; quarterly review | Documented policies, scoped deletion evidence and tests |
| Risk assessment | Company leadership | Annually and after material change | Signed risk register and remediation decisions |

## No-false-success requirements

1. Treat skipped, echo-only, or mock test output as **no evidence** of a production control.
2. Do not put live customer CSVs, cardholder information, webhook secrets, API tokens or private keys in public repositories, CI artifacts, issues, logs, or screenshots.
3. No production security-control bypass, payment movement, external outreach, or deployment solely to produce an audit screenshot.
4. Store real evidence in a restricted, access-controlled location with retention, source links, timestamps, and provenance; avoid exposing live sensitive data.
5. Do not assert a vendor control without verifying vendor configuration and responsibility boundaries.
6. Never mark a gap closed until an independently observable system state and an owner acceptance exist.

## Milestone sequence

1. **P0 — This week:** Remove deceptive payment automation in a reviewed PR; verify secrets/access roles and GitHub branch/environment protection; triage failed payment workflows and webhook risks.
2. **P1 — Next 30 days:** Confirm systems/services/data scope; approve asset, vendor, and access inventories; write incident, risk, access, retention and change-control policies; test backup alerts and a real isolated restore.
3. **P2 — Before auditor fieldwork:** Collect sustained operating evidence; sample changes, access reviews, incident exercises, vendor reviews and vulnerability remediations; conduct independent readiness assessment.
4. **Independent examination:** Engage a licensed independent CPA firm. Agree Type I vs Type II, Trust Services Criteria, scope, observation period and exceptions before making public SOC 2 claims.

## Key follow-up references

- `Garrettc123/garcar-payments`: proposed `compliance/soc2-readiness-20261125` branch
- AICPA Trust Services Criteria and official SOC 2 guidance: https://www.aicpa-cima.com/topic/audit-assurance/audit-and-assurance-greater-than-soc-2

**Assessment limit:** This is a point-in-time, limited connected-source code/config review; it is neither a penetration test nor a verification of cloud-account IAM, encryption, backups, or actual customer-data processing.
