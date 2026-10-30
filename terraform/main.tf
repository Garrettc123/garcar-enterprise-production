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

resource "aws_s3_bucket" "ledger_vault" {
  count               = var.enable_bucket_creation ? 1 : 0
  bucket              = var.ledger_bucket_name
  object_lock_enabled = true

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_versioning" "ledger_versioning" {
  count  = var.enable_bucket_creation ? 1 : 0
  bucket = aws_s3_bucket.ledger_vault[0].id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_public_access_block" "ledger_public_access" {
  count                   = var.enable_bucket_creation ? 1 : 0
  bucket                  = aws_s3_bucket.ledger_vault[0].id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "ledger_encryption" {
  count  = var.enable_bucket_creation ? 1 : 0
  bucket = aws_s3_bucket.ledger_vault[0].id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_object_lock_configuration" "ledger_lock_config" {
  count  = var.enable_bucket_creation ? 1 : 0
  bucket = aws_s3_bucket.ledger_vault[0].id
  rule {
    default_retention {
      mode = "COMPLIANCE"
      days = var.compliance_retention_days
    }
  }
  depends_on = [aws_s3_bucket_versioning.ledger_versioning]
}
