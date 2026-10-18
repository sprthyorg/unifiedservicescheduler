variable "cluster_name" {
  type = string
}

variable "region" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "secret_name_prefix" {
  description = "External Secrets may read only secrets under this prefix"
  type        = string
  default     = "scheduler/"
}

variable "secret_kms_key_arns" {
  description = "KMS keys that encrypt the readable secrets (from modules/database)"
  type        = list(string)
}

# Opt-out toggles: set false where the platform team already runs the add-on (ADR-007 §2).
variable "install_pod_identity_agent" {
  type    = bool
  default = true
}

variable "install_load_balancer_controller" {
  type    = bool
  default = true
}

variable "install_external_secrets" {
  type    = bool
  default = true
}

variable "install_argo_rollouts" {
  type    = bool
  default = true
}

variable "install_metrics_server" {
  type    = bool
  default = true
}

variable "chart_versions" {
  description = "Pinned Helm chart versions (bump deliberately; see deploy/CHANGELOG.md)"
  type = object({
    aws_load_balancer_controller = string
    external_secrets             = string
    argo_rollouts                = string
    metrics_server               = string
    raw                          = string
  })
  default = {
    aws_load_balancer_controller = "1.8.3"
    external_secrets             = "0.10.4"
    argo_rollouts                = "2.37.7" # app v1.7.2 — matches the kubectl plugin in ci-cd.yml
    metrics_server               = "3.12.2"
    raw                          = "2.0.0"
  }
}
