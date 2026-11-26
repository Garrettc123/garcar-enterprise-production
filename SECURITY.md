# Security Policy

Garcar Enterprise treats customer data, payment integrations, cloud credentials, and agent permissions as security-sensitive.

## Vulnerability reporting

**Do not disclose exploit details, credentials, personal data, or private security evidence in a public GitHub issue.** If private vulnerability reporting is enabled for this repository, select **Security → Report a vulnerability**. Otherwise, contact the project maintainer through an existing private, verified business channel. Do not send credentials or sensitive customer data in the initial report.

A report should identify affected components and versions, impact, reproducible steps using non-sensitive sample data, and a secure return contact. Receipt and remediation deadlines depend on triage and verified impact; an unpublished SLA must not be represented as an established control.

## Engineering security baseline (proposed; verify enforcement)

- Require GitHub multi-factor authentication for privileged users, least-privilege access and periodic access recertification. Service principals need named owners and revocation procedures.
- Protect the default branch against direct pushes and require reviewed pull requests, successful test/security checks, and conversation resolution. Confirm the actual GitHub rules; a CODEOWNERS file alone does not enforce review.
- Require an approved production deployment and independently verified post-deployment health checks. A successful workflow that prints text is not deployment evidence.
- Never store live API keys, webhook secrets, personal information or production customer files in Git. Use secret stores and scoped ephemeral credentials where feasible; revoke exposed keys immediately.
- Validate Stripe webhook signatures and event idempotency before recording any external payment. Do not claim revenue from test events or synthetic activity.
- Give AI agents no more access than required and keep high-risk actions behind explicit human approval, audit logs, and an emergency disable control.
- Document retention and deletion of customer CSVs, redaction of logs, encryption, backup/restore and breach response, with validated records.
- Track critical and high-severity vulnerabilities, compensating controls, owner decisions, and post-fix retesting.

## Incidents

If a suspected breach affects live credentials, customer records, payment webhooks, or agent privileges: (1) stop the relevant action or revoke affected credentials, (2) preserve available logs and timestamps, (3) identify systems and data at risk, (4) restore through a reviewed and verified change, and (5) assess applicable contractual and legal notification obligations with appropriate counsel. Preserve evidence and avoid public disclosure of sensitive details.

## Compliance statements

These are engineering and reporting expectations, **not proof that controls are implemented or operating effectively**. SOC 2 attainment can be claimed only on the basis of an appropriately scoped independent CPA-issued report. See `docs/compliance/SOC2_READINESS_2026-11-25.md` for verified observations and open gaps.
