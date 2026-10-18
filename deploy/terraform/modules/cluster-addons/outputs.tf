output "installed" {
  description = "Which add-ons this stack manages"
  value = {
    pod_identity_agent           = var.install_pod_identity_agent
    aws_load_balancer_controller = var.install_load_balancer_controller
    external_secrets             = var.install_external_secrets
    argo_rollouts                = var.install_argo_rollouts
    metrics_server               = var.install_metrics_server
  }
}
