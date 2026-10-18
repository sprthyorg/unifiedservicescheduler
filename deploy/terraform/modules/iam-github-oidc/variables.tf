variable "create_provider" {
  description = "Create the account-wide GitHub OIDC provider (exactly one stack per AWS account sets this — envs/shared)"
  type        = bool
  default     = false
}

variable "provider_arn" {
  description = "Existing GitHub OIDC provider ARN (when create_provider = false)"
  type        = string
  default     = null
}

variable "roles" {
  description = <<-EOT
    IAM roles GitHub Actions may assume. Key = role name.
      subjects            : allowed `sub` claims, e.g. "repo:ORG/REPO:environment:staging"
      policy_json         : optional inline policy
      managed_policy_arns : optional managed policies
      eks_access          : optional EKS access entries — cluster, access policy, and scope
                            (namespaces = [] means cluster-wide)
  EOT
  type = map(object({
    subjects            = list(string)
    policy_json         = optional(string)
    managed_policy_arns = optional(list(string), [])
    max_session_hours   = optional(number, 1)
    eks_access = optional(list(object({
      cluster_name      = string
      access_policy_arn = string
      namespaces        = optional(list(string), [])
    })), [])
  }))
}
