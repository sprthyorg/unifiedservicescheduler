# In-cluster controllers the scheduler manifests depend on (ADR-007 §2):
#   Ingress(alb) → AWS Load Balancer Controller · ExternalSecret → External Secrets Operator +
#   ClusterSecretStore "aws-secrets-manager" · Rollout/AnalysisTemplate → Argo Rollouts · HPA → metrics-server
# AWS permissions use EKS Pod Identity (no IRSA OIDC issuer setup needed).
data "aws_caller_identity" "current" {}

resource "aws_eks_addon" "pod_identity_agent" {
  count        = var.install_pod_identity_agent ? 1 : 0
  cluster_name = var.cluster_name
  addon_name   = "eks-pod-identity-agent"
}

# ---------------------------------------------------------------- AWS Load Balancer Controller
module "lbc_pod_identity" {
  source  = "terraform-aws-modules/eks-pod-identity/aws"
  version = "~> 1.4"
  count   = var.install_load_balancer_controller ? 1 : 0

  name                            = "${var.cluster_name}-aws-lbc"
  attach_aws_lb_controller_policy = true
  associations = {
    this = {
      cluster_name    = var.cluster_name
      namespace       = "kube-system"
      service_account = "aws-load-balancer-controller"
    }
  }
}

resource "helm_release" "aws_load_balancer_controller" {
  count      = var.install_load_balancer_controller ? 1 : 0
  name       = "aws-load-balancer-controller"
  repository = "https://aws.github.io/eks-charts"
  chart      = "aws-load-balancer-controller"
  version    = var.chart_versions.aws_load_balancer_controller
  namespace  = "kube-system"
  values = [yamlencode({
    clusterName    = var.cluster_name
    region         = var.region
    vpcId          = var.vpc_id
    serviceAccount = { create = true, name = "aws-load-balancer-controller" }
  })]
  depends_on = [aws_eks_addon.pod_identity_agent, module.lbc_pod_identity]
}

# ---------------------------------------------------------------- External Secrets Operator
module "eso_pod_identity" {
  source  = "terraform-aws-modules/eks-pod-identity/aws"
  version = "~> 1.4"
  count   = var.install_external_secrets ? 1 : 0

  name                                  = "${var.cluster_name}-external-secrets"
  attach_external_secrets_policy        = true
  external_secrets_create_permission    = false
  external_secrets_secrets_manager_arns = ["arn:aws:secretsmanager:${var.region}:${data.aws_caller_identity.current.account_id}:secret:${var.secret_name_prefix}*"]
  external_secrets_kms_key_arns         = var.secret_kms_key_arns
  associations = {
    this = {
      cluster_name    = var.cluster_name
      namespace       = "external-secrets"
      service_account = "external-secrets"
    }
  }
}

resource "helm_release" "external_secrets" {
  count            = var.install_external_secrets ? 1 : 0
  name             = "external-secrets"
  repository       = "https://charts.external-secrets.io"
  chart            = "external-secrets"
  version          = var.chart_versions.external_secrets
  namespace        = "external-secrets"
  create_namespace = true
  values = [yamlencode({
    installCRDs    = true
    serviceAccount = { create = true, name = "external-secrets" }
  })]
  depends_on = [aws_eks_addon.pod_identity_agent, module.eso_pod_identity]
}

# The ClusterSecretStore is a CRD instance: installed through the generic "raw" chart so that
# `terraform plan` works before the CRD exists (kubernetes_manifest would fail on first plan).
resource "helm_release" "cluster_secret_store" {
  count      = var.install_external_secrets ? 1 : 0
  name       = "scheduler-cluster-secret-store"
  repository = "https://bedag.github.io/helm-charts"
  chart      = "raw"
  version    = var.chart_versions.raw
  namespace  = "external-secrets"
  values = [yamlencode({
    resources = [{
      apiVersion = "external-secrets.io/v1beta1"
      kind       = "ClusterSecretStore"
      metadata   = { name = "aws-secrets-manager" } # referenced by deploy/k8s/base/external-secret.yaml
      spec = {
        provider = { aws = { service = "SecretsManager", region = var.region } }
        # no auth block → the controller's Pod Identity credentials are used
      }
    }]
  })]
  depends_on = [helm_release.external_secrets]
}

# ---------------------------------------------------------------- Argo Rollouts (production canary, ADR-006)
resource "helm_release" "argo_rollouts" {
  count            = var.install_argo_rollouts ? 1 : 0
  name             = "argo-rollouts"
  repository       = "https://argoproj.github.io/argo-helm"
  chart            = "argo-rollouts"
  version          = var.chart_versions.argo_rollouts
  namespace        = "argo-rollouts"
  create_namespace = true
  values           = [yamlencode({ dashboard = { enabled = false } })]
}

# ---------------------------------------------------------------- metrics-server (HPA, NFR-04)
resource "helm_release" "metrics_server" {
  count      = var.install_metrics_server ? 1 : 0
  name       = "metrics-server"
  repository = "https://kubernetes-sigs.github.io/metrics-server/"
  chart      = "metrics-server"
  version    = var.chart_versions.metrics_server
  namespace  = "kube-system"
}
