# Staging infrastructure for the Unified Service Scheduler (ADR-006, ADR-007; NFR-07, NFR-08, NFR-11).
# Creates: RDS PostgreSQL + generated credentials · cluster add-ons · app namespace · GitHub deploy role.
# Assumes the platform team's VPC and EKS cluster (read via remote state / data sources).
terraform {
  required_version = ">= 1.8"
  required_providers {
    aws    = { source = "hashicorp/aws", version = "~> 5.60" }
    helm   = { source = "hashicorp/helm", version = "~> 2.15" }
    random = { source = "hashicorp/random", version = "~> 3.6" }
  }
  backend "s3" {
    bucket         = "ORG-terraform-state"
    key            = "unified-service-scheduler/staging.tfstate"
    region         = "ap-south-1"
    dynamodb_table = "terraform-locks"
    encrypt        = true
  }
}

variable "github_repository" {
  type    = string
  default = "ORG/unified-service-scheduler"
}

variable "cluster_name" {
  type    = string
  default = "ownership-staging"
}

variable "network_state_key" {
  description = "Platform team's network state (outputs: vpc_id, data_subnet_ids, eks_node_security_group_id)"
  type        = string
  default     = "platform/network-staging.tfstate"
}

locals {
  environment = "staging"
  namespace   = "scheduler-staging"
  region      = "ap-south-1" # data residency India (C-02)
  db = {                     # smaller and single-AZ (cost); PITR still on
    instance_class           = "db.t4g.medium"
    allocated_storage_gb     = 50
    max_allocated_storage_gb = 100
    multi_az                 = false
    backup_retention_days    = 7
    deletion_protection      = false
  }
}

provider "aws" {
  region = local.region
  default_tags { tags = { system = "unified-service-scheduler", env = local.environment, owner = "ownership-domain" } }
}

data "aws_eks_cluster" "this" {
  name = var.cluster_name
}

data "aws_eks_cluster_auth" "this" {
  name = var.cluster_name
}

provider "helm" {
  kubernetes {
    host                   = data.aws_eks_cluster.this.endpoint
    cluster_ca_certificate = base64decode(data.aws_eks_cluster.this.certificate_authority[0].data)
    token                  = data.aws_eks_cluster_auth.this.token
  }
}

data "terraform_remote_state" "network" {
  backend = "s3"
  config  = { bucket = "ORG-terraform-state", key = var.network_state_key, region = local.region }
}

data "terraform_remote_state" "shared" {
  backend = "s3"
  config  = { bucket = "ORG-terraform-state", key = "unified-service-scheduler/shared.tfstate", region = local.region }
}

# ---------------------------------------------------------------- database (modules/database)
module "database" {
  source                     = "../../modules/database"
  environment                = local.environment
  vpc_id                     = data.terraform_remote_state.network.outputs.vpc_id
  subnet_ids                 = data.terraform_remote_state.network.outputs.data_subnet_ids
  allowed_security_group_ids = [data.terraform_remote_state.network.outputs.eks_node_security_group_id]
  instance_class             = local.db.instance_class
  allocated_storage_gb       = local.db.allocated_storage_gb
  max_allocated_storage_gb   = local.db.max_allocated_storage_gb
  multi_az                   = local.db.multi_az
  backup_retention_days      = local.db.backup_retention_days
  deletion_protection        = local.db.deletion_protection
}

# ---------------------------------------------------------------- cluster add-ons (ADR-007 §2)
module "cluster_addons" {
  source              = "../../modules/cluster-addons"
  cluster_name        = var.cluster_name
  region              = local.region
  vpc_id              = data.terraform_remote_state.network.outputs.vpc_id
  secret_kms_key_arns = [module.database.kms_key_arn]
  # Set any install_* = false if the platform team already runs that add-on on this cluster.
}

# The app namespace is created here (not by Kustomize) so the deploy role can be namespace-scoped.
resource "helm_release" "namespace" {
  name       = "scheduler-namespace"
  repository = "https://bedag.github.io/helm-charts"
  chart      = "raw"
  version    = "2.0.0"
  namespace  = "default"
  values = [yamlencode({
    resources = [{
      apiVersion = "v1"
      kind       = "Namespace"
      metadata = {
        name        = local.namespace
        labels      = { "pod-security.kubernetes.io/enforce" = "restricted" }
        annotations = { "helm.sh/resource-policy" = "keep" } # never delete app data with the release
      }
    }]
  })]
}

# ---------------------------------------------------------------- GitHub deploy role (ci-cd.yml)
data "aws_iam_policy_document" "deploy" {
  statement {
    actions   = ["eks:DescribeCluster"] # aws eks update-kubeconfig
    resources = [data.aws_eks_cluster.this.arn]
  }
}

module "deploy_role" {
  source       = "../../modules/iam-github-oidc"
  provider_arn = data.terraform_remote_state.shared.outputs.github_oidc_provider_arn
  roles = {
    "uss-deploy-staging" = {
      # only jobs in the "staging" GitHub environment may assume it
      subjects    = ["repo:${var.github_repository}:environment:staging"]
      policy_json = data.aws_iam_policy_document.deploy.json
      eks_access = [{
        cluster_name      = var.cluster_name
        access_policy_arn = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSAdminPolicy"
        namespaces        = [local.namespace]
      }]
    }
  }
}

# ---------------------------------------------------------------- outputs
output "deploy_role_arn" {
  description = "GitHub variable DEPLOY_ROLE_ARN"
  value       = module.deploy_role.role_arns["uss-deploy-staging"]
}

output "db_address" {
  value = module.database.address
}

output "db_secret_arns" {
  value = { admin = module.database.admin_secret_arn, app = module.database.app_secret_arn }
}

output "cluster_addons" {
  value = module.cluster_addons.installed
}
