data "aws_iam_policy_document" "ledger_runtime" {
  statement {
    sid = "ReadLedgerBucketControls"
    actions = [
      "s3:GetBucketLocation",
      "s3:GetBucketVersioning",
      "s3:GetObjectLockConfiguration",
      "s3:GetEncryptionConfiguration",
      "s3:GetBucketPublicAccessBlock",
    ]
    resources = ["arn:aws:s3:::${var.ledger_bucket_name}"]
  }

  statement {
    sid       = "ListLedgerEvents"
    actions   = ["s3:ListBucket"]
    resources = ["arn:aws:s3:::${var.ledger_bucket_name}"]

    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values = [
        "evidence/chain/events/*",
        "evidence/chain/idempotency/*",
        "evidence/chain/receipts/*",
      ]
    }
  }

  statement {
    sid = "ReadAndAppendEvidenceObjects"
    actions = [
      "s3:GetObject",
      "s3:GetObjectVersion",
      "s3:GetObjectRetention",
      "s3:PutObject",
    ]
    resources = ["arn:aws:s3:::${var.ledger_bucket_name}/evidence/*"]
  }
}

resource "aws_iam_policy" "ledger_runtime" {
  name        = "garcar-enterprise-ledger-runtime"
  description = "Least-privilege S3 access for the guarded Garcar evidence gateway"
  policy      = data.aws_iam_policy_document.ledger_runtime.json
}

output "ledger_runtime_policy_arn" {
  description = "Attach this managed policy to the dedicated workload role used by the gateway."
  value       = aws_iam_policy.ledger_runtime.arn
}
