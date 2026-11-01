"""Static policy-contract tests; cloud integration tests require an isolated AWS test account."""
from pathlib import Path

SOURCE = Path("src/main.py").read_text()
COMPOSE = Path("docker-compose.yml").read_text()
TERRAFORM = Path("terraform/main.tf").read_text()
POLICY = Path("src/rhns_policy.py").read_text()
IAM_POLICY = Path("terraform/iam.tf").read_text()


def test_no_fake_credentials_or_dev_root_token():
    forbidden = ["sk_test_placeholder", "mock_access_key", "mock_secret_key", "dev-root-token", "dev-token"]
    combined = SOURCE + COMPOSE
    assert all(value not in combined for value in forbidden)


def test_fail_closed_vault_and_no_environment_fallback():
    assert "refusing fallback credentials" in SOURCE
    assert "load_runtime_config()" in SOURCE
    assert "STRIPE_SECRET_KEY" not in SOURCE
    assert "API_BEARER_TOKEN = os.getenv" not in SOURCE


def test_review_required_and_no_outreach_execution():
    assert '"HUMAN_REVIEW_REQUIRED"' in POLICY
    assert '"NOT_GRANTED"' in SOURCE
    assert '"NOT_SENT"' in SOURCE
    assert "stripe.api_key" not in SOURCE.lower()


def test_object_lock_and_versioning_verified():
    assert "get_object_lock_configuration" in SOURCE
    assert "get_bucket_versioning" in SOURCE
    assert 'retention.get("Mode") != "COMPLIANCE"' in SOURCE


def test_terraform_creation_is_opt_in_and_protected():
    assert "default     = false" in Path("terraform/variables.tf").read_text()
    assert "prevent_destroy = true" in TERRAFORM
    assert "object_lock_enabled = true" in TERRAFORM



def test_runtime_iam_is_read_append_only_and_prefix_scoped():
    required = [
        "s3:GetBucketObjectLockConfiguration",
        "s3:GetObjectRetention",
        "evidence/chain/events/",
        "evidence/chain/idempotency/",
        "evidence/chain/receipts/",
    ]
    assert all(value in IAM_POLICY for value in required)
    assert "s3:DeleteObject" not in IAM_POLICY
    assert "s3:DeleteObjectVersion" not in IAM_POLICY
    assert "s3:PutBucketObjectLockConfiguration" not in IAM_POLICY
    assert "s3:PutObjectRetention" not in IAM_POLICY


def test_kms_encryption_is_not_claimed_as_ready_without_kms_policy():
    assert 'value != "AES256"' in SOURCE
    assert "KMS requires a separately reviewed runtime policy" in SOURCE
