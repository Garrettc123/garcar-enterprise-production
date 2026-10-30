variable "aws_region" {
  description = "AWS region for the immutable evidence bucket."
  type        = string
  default     = "us-east-1"
}

variable "ledger_bucket_name" {
  description = "Globally unique S3 bucket name. Must be supplied explicitly."
  type        = string
  nullable    = false
}

variable "compliance_retention_days" {
  description = "Default S3 Object Lock COMPLIANCE retention in days. Irreversible for retained objects."
  type        = number
  nullable    = false
  validation {
    condition     = var.compliance_retention_days >= 1 && var.compliance_retention_days <= 3650
    error_message = "Retention must be between 1 and 3650 days."
  }
}

variable "enable_bucket_creation" {
  description = "Must be explicitly true before Terraform is allowed to create the bucket."
  type        = bool
  default     = false
}
