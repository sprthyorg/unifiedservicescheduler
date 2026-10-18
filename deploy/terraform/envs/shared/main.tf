# Account-level resources shared by staging and production (ADR-007, ADR-008):
#   GitHub OIDC provider (one per account) · ECR repository · CI roles (ECR push, Terraform plan/apply)
# Day 0: the FIRST apply of this stack is run once by an account administrator, because it creates
# the roles the infra pipeline itself assumes. After that, infra.yml manages it like any other stack.
terraform {
  required_version = ">= 1.8"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.60" }
  }
  backend "s3" {
    bucket         = "ORG-terraform-state"
    key            = "unified-service-scheduler/shared.tfstate"
    region         = "ap-south-1"
    dynamodb_table = "terraform-locks"
    encrypt        = true
  }
}

provider "aws" {
  region = "ap-south-1"
  default_tags { tags = { system = "unified-service-scheduler", env = "shared", owner = "ownership-domain" } }
}

variable "github_repository" {
  description = "owner/name of the GitHub repository allowed to assume the CI roles"
  type        = string
  default     = "ORG/unified-service-scheduler"
}

variable "state_bucket" {
  type    = string
  default = "ORG-terraform-state"
}

variable "lock_table" {
  type    = string
  default = "terraform-locks"
}

variable "cluster_names" {
  description = "EKS clusters the Terraform roles need Kubernetes access to (helm_release)"
  type        = list(string)
  default     = ["ownership-staging", "ownership-prod"]
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  repo    = var.github_repository
  account = data.aws_caller_identity.current.account_id
  region  = data.aws_region.current.name
}

# ---------------------------------------------------------------- container registry (ADR-008)
resource "aws_kms_key" "ecr" {
  description         = "unified-service-scheduler ECR images"
  enable_key_rotation = true
}

resource "aws_ecr_repository" "scheduler" {
  name                 = "unified-service-scheduler/scheduler-service"
  image_tag_mutability = "IMMUTABLE"
  image_scanning_configuration { scan_on_push = true }
  encryption_configuration {
    encryption_type = "KMS"
    kms_key         = aws_kms_key.ecr.arn
  }
}

resource "aws_ecr_lifecycle_policy" "scheduler" {
  repository = aws_ecr_repository.scheduler.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "keep the last 50 images"
      selection    = { tagStatus = "any", countType = "imageCountMoreThan", countNumber = 50 }
      action       = { type = "expire" }
    }]
  })
}

# ---------------------------------------------------------------- CI roles
data "aws_iam_policy_document" "ecr_push" {
  statement {
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }
  statement {
    actions = [
      "ecr:BatchCheckLayerAvailability", "ecr:BatchGetImage", "ecr:CompleteLayerUpload",
      "ecr:DescribeImages", "ecr:GetDownloadUrlForLayer", "ecr:InitiateLayerUpload",
      "ecr:PutImage", "ecr:UploadLayerPart",
    ]
    resources = [aws_ecr_repository.scheduler.arn]
  }
  statement {
    actions   = ["kms:GenerateDataKey", "kms:Decrypt"]
    resources = [aws_kms_key.ecr.arn]
  }
}

data "aws_iam_policy_document" "terraform_plan" {
  statement {
    sid       = "StateRead"
    actions   = ["s3:GetObject", "s3:ListBucket"]
    resources = ["arn:aws:s3:::${var.state_bucket}", "arn:aws:s3:::${var.state_bucket}/unified-service-scheduler/*", "arn:aws:s3:::${var.state_bucket}/platform/*"]
  }
  statement {
    sid       = "StateLock"
    actions   = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:DeleteItem"]
    resources = ["arn:aws:dynamodb:${local.region}:${local.account}:table/${var.lock_table}"]
  }
  statement {
    sid       = "RefreshGeneratedSecrets" # ReadOnlyAccess excludes secret values (ADR-007 consequences)
    actions   = ["secretsmanager:GetSecretValue"]
    resources = ["arn:aws:secretsmanager:${local.region}:${local.account}:secret:scheduler/*"]
  }
  statement {
    actions   = ["kms:Decrypt"]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "kms:ViaService"
      values   = ["secretsmanager.${local.region}.amazonaws.com", "s3.${local.region}.amazonaws.com"]
    }
  }
}

module "github_oidc" {
  source          = "../../modules/iam-github-oidc"
  create_provider = true
  roles = {
    "uss-ecr-push" = {
      subjects    = ["repo:${local.repo}:ref:refs/heads/main"]
      policy_json = data.aws_iam_policy_document.ecr_push.json
    }
    "uss-terraform-plan" = {
      subjects            = ["repo:${local.repo}:pull_request"]
      managed_policy_arns = ["arn:aws:iam::aws:policy/ReadOnlyAccess"]
      policy_json         = data.aws_iam_policy_document.terraform_plan.json
      eks_access = [for c in var.cluster_names : {
        cluster_name      = c
        access_policy_arn = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSAdminViewPolicy"
      }]
    }
    "uss-terraform-apply" = {
      # Only jobs running in the approval-gated infra-* GitHub environments can assume this role.
      subjects = [for e in ["infra-shared", "infra-staging", "infra-production"] : "repo:${local.repo}:environment:${e}"]
      # Broad by necessity (creates IAM, RDS, KMS, EKS access). Follow-up: permissions boundary.
      managed_policy_arns = ["arn:aws:iam::aws:policy/AdministratorAccess"]
      eks_access = [for c in var.cluster_names : {
        cluster_name      = c
        access_policy_arn = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"
      }]
    }
  }
}

output "github_oidc_provider_arn" {
  value = module.github_oidc.provider_arn
}

output "ecr_registry" {
  description = "GitHub variable ECR_REGISTRY"
  value       = split("/", aws_ecr_repository.scheduler.repository_url)[0]
}

output "ecr_repository_url" {
  value = aws_ecr_repository.scheduler.repository_url
}

output "ecr_push_role_arn" {
  description = "GitHub variable ECR_PUSH_ROLE_ARN"
  value       = module.github_oidc.role_arns["uss-ecr-push"]
}

output "terraform_plan_role_arn" {
  description = "GitHub variable TF_PLAN_ROLE_ARN"
  value       = module.github_oidc.role_arns["uss-terraform-plan"]
}

output "terraform_apply_role_arn" {
  description = "GitHub variable TF_APPLY_ROLE_ARN"
  value       = module.github_oidc.role_arns["uss-terraform-apply"]
}
