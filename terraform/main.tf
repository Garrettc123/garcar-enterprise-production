terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

resource "aws_s3_bucket" "ledger" {
  bucket              = var.ledger_bucket_name
  object_lock_enabled = true
  force_destroy       = false

  tags = {
    System      = "GarcarEnterprise"
    Environment = var.environment
    DataClass   = "ImmutableAuditLedger"
  }
}

resource "aws_s3_bucket_public_access_block" "ledger" {
  bucket                  = aws_s3_bucket.ledger.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "ledger" {
  bucket = aws_s3_bucket.ledger.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "ledger" {
  bucket = aws_s3_bucket.ledger.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms"
    }
  }
}

resource "aws_s3_bucket_object_lock_configuration" "ledger" {
  bucket = aws_s3_bucket.ledger.id

  rule {
    default_retention {
      mode = "COMPLIANCE"
      days = var.retention_days
    }
  }

  depends_on = [aws_s3_bucket_versioning.ledger]
}

output "ledger_bucket_name" {
  value = aws_s3_bucket.ledger.id
}
