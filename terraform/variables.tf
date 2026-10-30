variable "aws_region" { type = string; default = "us-east-1" }
variable "ledger_bucket_name" { type = string }
variable "retention_days" { type = number; default = 365; validation { condition = var.retention_days >= 1 && var.retention_days <= 36500; error_message = "retention_days must be between 1 and 36500" } }
variable "environment" { type = string; default = "production" }
