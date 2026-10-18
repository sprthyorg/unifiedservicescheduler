# RDS PostgreSQL 16 for scheduler-service, plus generated credentials (ADR-007 §3).
# Secrets written here are consumed by External Secrets in deploy/k8s/base/external-secret.yaml:
#   scheduler/<env>/db-admin  → db-bootstrap init container only
#   scheduler/<env>/db        → API (app_url) and Flyway (flyway_*)
locals {
  name = "scheduler-${var.environment}"
}

resource "aws_kms_key" "this" {
  description         = "${local.name}: database storage and secrets"
  enable_key_rotation = true
}

resource "aws_kms_alias" "this" {
  name          = "alias/${local.name}"
  target_key_id = aws_kms_key.this.key_id
}

resource "aws_db_subnet_group" "this" {
  name       = local.name
  subnet_ids = var.subnet_ids
}

resource "aws_db_parameter_group" "this" {
  name   = "${local.name}-pg16"
  family = "postgres16"
  parameter {
    name  = "log_min_duration_statement"
    value = "250" # ms — surfaces slow queries (NFR-02)
  }
  parameter {
    name         = "rds.force_ssl"
    value        = "1" # TLS in transit (NFR-08)
    apply_method = "pending-reboot"
  }
}

resource "aws_security_group" "db" {
  name        = "${local.name}-db"
  description = "PostgreSQL for ${local.name}"
  vpc_id      = var.vpc_id
}

resource "aws_vpc_security_group_ingress_rule" "postgres" {
  for_each                     = toset(var.allowed_security_group_ids)
  security_group_id            = aws_security_group.db.id
  referenced_security_group_id = each.value
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
  description                  = "PostgreSQL from EKS"
}

# --- credentials (alphanumeric: safe inside URLs and JDBC strings) ------------------------------
resource "random_password" "admin" {
  length  = 32
  special = false
}

resource "random_password" "owner" {
  length  = 32
  special = false
}

resource "random_password" "app" {
  length  = 32
  special = false
}

resource "aws_db_instance" "this" {
  identifier                   = local.name
  engine                       = "postgres"
  engine_version               = var.engine_version
  instance_class               = var.instance_class
  allocated_storage            = var.allocated_storage_gb
  max_allocated_storage        = var.max_allocated_storage_gb
  storage_type                 = "gp3"
  storage_encrypted            = true
  kms_key_id                   = aws_kms_key.this.arn
  multi_az                     = var.multi_az
  db_subnet_group_name         = aws_db_subnet_group.this.name
  vpc_security_group_ids       = [aws_security_group.db.id]
  parameter_group_name         = aws_db_parameter_group.this.name
  backup_retention_period      = var.backup_retention_days # PITR ⇒ RPO ≤ 5 min (NFR-07)
  backup_window                = var.backup_window
  maintenance_window           = var.maintenance_window
  deletion_protection          = var.deletion_protection
  skip_final_snapshot          = !var.deletion_protection
  final_snapshot_identifier    = var.deletion_protection ? "${local.name}-final" : null
  copy_tags_to_snapshot        = true
  performance_insights_enabled = true
  auto_minor_version_upgrade   = true
  username                     = "scheduler_admin"
  password                     = random_password.admin.result
  db_name                      = var.db_name
}

resource "aws_secretsmanager_secret" "admin" {
  name        = "scheduler/${var.environment}/db-admin"
  description = "RDS master credentials — read only by the db-bootstrap init container"
  kms_key_id  = aws_kms_key.this.arn
}

resource "aws_secretsmanager_secret_version" "admin" {
  secret_id = aws_secretsmanager_secret.admin.id
  secret_string = jsonencode({
    host     = aws_db_instance.this.address
    port     = aws_db_instance.this.port
    dbname   = var.db_name
    username = aws_db_instance.this.username
    password = random_password.admin.result
  })
}

resource "aws_secretsmanager_secret" "app" {
  name        = "scheduler/${var.environment}/db"
  description = "scheduler_owner (Flyway) and scheduler_app (API) credentials"
  kms_key_id  = aws_kms_key.this.arn
}

resource "aws_secretsmanager_secret_version" "app" {
  secret_id = aws_secretsmanager_secret.app.id
  secret_string = jsonencode({
    owner_user      = var.owner_role
    owner_password  = random_password.owner.result
    app_user        = var.app_role
    app_password    = random_password.app.result
    flyway_user     = var.owner_role
    flyway_password = random_password.owner.result
    flyway_jdbc_url = "jdbc:postgresql://${aws_db_instance.this.address}:${aws_db_instance.this.port}/${var.db_name}?sslmode=require"
    app_url         = "postgresql://${var.app_role}:${random_password.app.result}@${aws_db_instance.this.address}:${aws_db_instance.this.port}/${var.db_name}?sslmode=require"
  })
}
