output "provider_arn" {
  value = local.provider_arn
}

output "role_arns" {
  description = "Role name → ARN"
  value       = { for k, r in aws_iam_role.this : k => r.arn }
}
