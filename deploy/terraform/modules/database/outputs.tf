output "address" {
  value = aws_db_instance.this.address
}

output "port" {
  value = aws_db_instance.this.port
}

output "security_group_id" {
  value = aws_security_group.db.id
}

output "kms_key_arn" {
  value = aws_kms_key.this.arn
}

output "admin_secret_arn" {
  value = aws_secretsmanager_secret.admin.arn
}

output "app_secret_arn" {
  value = aws_secretsmanager_secret.app.arn
}
