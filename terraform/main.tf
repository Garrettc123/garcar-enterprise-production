terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
}
provider "aws" { region = "us-east-1" }

resource "aws_s3_bucket" "ledger_vault" {
  bucket = "garcar-enterprise-immutable-ledger"
  object_lock_enabled = true
}

resource "aws_s3_bucket_versioning" "ledger_versioning" {
  bucket = aws_s3_bucket.ledger_vault.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_object_lock_configuration" "ledger_lock_config" {
  bucket = aws_s3_bucket.ledger_vault.id
  rule {
    default_retention { mode = "COMPLIANCE"; years = 1 }
  }
  depends_on = [aws_s3_bucket_versioning.ledger_versioning]
}
