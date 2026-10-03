"""GAR-530 static guard: new dial/send/charge code must go through approval_gate.

Fails if a source file contains an outbound send/charge/dial pattern but never
references ``approval_gate``. Also fails if an auto-merge workflow comes back.
"""
import re
from pathlib import Path

from conftest import ROOT

SKIP_DIRS = {".git", "node_modules", "venv", ".venv", "__pycache__", "tests", "approval_gate"}

PY_PATTERNS = re.compile(
    r"smtplib\.SMTP|\.sendmail\(|api\.sendgrid\.com|api\.resend\.com|api\.postmarkapp\.com"
    r"|stripe\.[A-Za-z_.]+\.create\(|stripe\.Transfer|stripe\.Payout|/v1/charges|commerce\.coinbase\.com/charges"
    r"|docusign|api\.bland\.ai|bland\.ai/v1/calls|api\.twilio\.com|twilio\.rest|messages\.create\(",
    re.IGNORECASE,
)
JS_PATTERNS = re.compile(
    r"api\.sendgrid\.com|api\.resend\.com|@sendgrid/mail|resend\.emails\.send|nodemailer"
    r"|stripe\.(paymentIntents|checkout\.sessions|transfers|payouts|invoices|charges)\.create"
    r"|/v1/charges|docusign|api\.bland\.ai|api\.twilio\.com",
    re.IGNORECASE,
)
MERGE_PATTERNS = re.compile(
    r"pascalgn/automerge-action|hmarr/auto-approve-action|gh pr merge|enable-pull-request-automerge"
    r"|peter-evans/enable-pull-request-automerge|--auto\b.*merge|merge_method",
    re.IGNORECASE,
)


def _files(exts):
    for path in ROOT.rglob("*"):
        if path.suffix in exts and path.is_file() and not (set(path.relative_to(ROOT).parts) & SKIP_DIRS):
            yield path


def _offenders(exts, pattern):
    bad = []
    for path in _files(exts):
        text = path.read_text(encoding="utf-8", errors="replace")
        if pattern.search(text) and "approval_gate" not in text:
            bad.append(f"{path.relative_to(ROOT)}: {pattern.search(text).group(0)}")
    return bad


def test_python_send_charge_dial_sites_import_approval_gate():
    assert _offenders({".py"}, PY_PATTERNS) == []


def test_js_send_charge_dial_sites_reference_approval_gate():
    assert _offenders({".js", ".mjs", ".ts"}, JS_PATTERNS) == []


def test_no_auto_merge_workflows():
    wf = ROOT / ".github" / "workflows"
    bad = [p.name for p in wf.glob("*.y*ml") if MERGE_PATTERNS.search(p.read_text())]
    assert bad == []


def test_guard_actually_detects_ungated_code(tmp_path):
    sample = 'import stripe\nstripe.PaymentIntent.create(amount=1)\n'
    assert PY_PATTERNS.search(sample) and "approval_gate" not in sample


def test_codeowners_requires_garrett():
    text = (ROOT / ".github" / "CODEOWNERS").read_text()
    assert re.search(r"^\*\s+@Garrettc123\s*$", text, re.MULTILINE)
