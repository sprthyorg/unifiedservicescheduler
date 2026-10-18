variable "environment" {
  description = "staging | production — used in names and secret paths (scheduler/<environment>/…)"
  type        = string
  validation {
    condition     = contains(["staging", "production"], var.environment)
    error_message = "environment must be staging or production."
  }
}

variable "vpc_id" {
  type = string
}

variable "subnet_ids" {
  description = "Private data subnets for the DB subnet group (≥ 2 AZs)"
  type        = list(string)
}

variable "allowed_security_group_ids" {
  description = "Security groups allowed to reach PostgreSQL on 5432 (EKS nodes / pods)"
  type        = list(string)
}

variable "instance_class" {
  type = string
}

variable "allocated_storage_gb" {
  type = number
}

variable "max_allocated_storage_gb" {
  type = number
}

variable "multi_az" {
  type = bool
}

variable "backup_retention_days" {
  type = number
}

variable "deletion_protection" {
  type = bool
}

variable "engine_version" {
  type    = string
  default = "16.4"
}

variable "db_name" {
  type    = string
  default = "scheduler"
}

variable "owner_role" {
  description = "PostgreSQL role that owns the schema and runs Flyway (DDL)"
  type        = string
  default     = "scheduler_owner"
}

variable "app_role" {
  description = "PostgreSQL role used by the API (DML only)"
  type        = string
  default     = "scheduler_app"
}

variable "backup_window" {
  type    = string
  default = "20:30-21:30" # 02:00–03:00 IST
}

variable "maintenance_window" {
  type    = string
  default = "sun:21:30-sun:22:30"
}
