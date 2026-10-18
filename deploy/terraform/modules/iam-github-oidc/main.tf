# GitHub Actions → AWS via OIDC: short-lived credentials, no stored keys (NFR-08, ADR-007).
resource "aws_iam_openid_connect_provider" "github" {
  count          = var.create_provider ? 1 : 0
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
  # AWS validates GitHub's certificate chain itself; the thumbprint is required by the API but unused.
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]
}

locals {
  provider_arn = var.create_provider ? aws_iam_openid_connect_provider.github[0].arn : var.provider_arn

  managed = merge({}, [
    for name, r in var.roles : { for arn in r.managed_policy_arns : "${name}|${arn}" => { role = name, arn = arn } }
  ]...)

  access = merge({}, [
    for name, r in var.roles : { for a in r.eks_access : "${name}|${a.cluster_name}" => merge(a, { role = name }) }
  ]...)
}

data "aws_iam_policy_document" "trust" {
  for_each = var.roles
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [local.provider_arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = each.value.subjects
    }
  }
}

resource "aws_iam_role" "this" {
  for_each             = var.roles
  name                 = each.key
  assume_role_policy   = data.aws_iam_policy_document.trust[each.key].json
  max_session_duration = each.value.max_session_hours * 3600
  lifecycle {
    precondition {
      condition     = local.provider_arn != null
      error_message = "Set create_provider = true or pass provider_arn."
    }
  }
}

resource "aws_iam_role_policy" "inline" {
  for_each = { for k, v in var.roles : k => v if v.policy_json != null }
  name     = "${each.key}-inline"
  role     = aws_iam_role.this[each.key].id
  policy   = each.value.policy_json
}

resource "aws_iam_role_policy_attachment" "managed" {
  for_each   = local.managed
  role       = aws_iam_role.this[each.value.role].name
  policy_arn = each.value.arn
}

resource "aws_eks_access_entry" "this" {
  for_each      = local.access
  cluster_name  = each.value.cluster_name
  principal_arn = aws_iam_role.this[each.value.role].arn
  type          = "STANDARD"
}

resource "aws_eks_access_policy_association" "this" {
  for_each      = local.access
  cluster_name  = each.value.cluster_name
  principal_arn = aws_iam_role.this[each.value.role].arn
  policy_arn    = each.value.access_policy_arn
  access_scope {
    type       = length(each.value.namespaces) == 0 ? "cluster" : "namespace"
    namespaces = length(each.value.namespaces) == 0 ? null : each.value.namespaces
  }
  depends_on = [aws_eks_access_entry.this]
}
