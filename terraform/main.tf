terraform {
  required_version = ">= 1.6"
  # For team use, configure a remote backend (S3 + DynamoDB lock) here.
  required_providers { aws = { source = "hashicorp/aws", version = "~> 5.0" } }
}
provider "aws" {
  region = var.region
  default_tags { tags = { Project = var.name, ManagedBy = "terraform" } }
}

variable "region" { default = "us-east-1" }
variable "name"   { default = "rag-on-aws" }
variable "admin_cidrs" {
  description = "CIDRs allowed to reach the EKS API endpoint (set to your public IP /32)"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"
  name    = var.name
  cidr    = "10.0.0.0/16"
  azs             = ["${var.region}a", "${var.region}b"]
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24"]
  enable_nat_gateway = true
  single_nat_gateway = true
}

module "eks" {
  source          = "terraform-aws-modules/eks/aws"
  version         = "~> 20.0"
  cluster_name    = var.name
  cluster_version = "1.30"
  vpc_id          = module.vpc.vpc_id
  subnet_ids      = module.vpc.private_subnets
  cluster_endpoint_public_access       = true
  cluster_endpoint_public_access_cidrs = var.admin_cidrs
  cluster_enabled_log_types            = ["api", "audit", "authenticator"]
  cluster_addons = {
    aws-ebs-csi-driver = { most_recent = true, service_account_role_arn = module.ebs_csi_irsa.iam_role_arn }
  }
  enable_cluster_creator_admin_permissions = true
  eks_managed_node_groups = {
    default = { instance_types = ["t3.large"], min_size = 1, max_size = 3, desired_size = 2 }
  }
}

module "ebs_csi_irsa" {
  source                = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version               = "~> 5.0"
  role_name             = "${var.name}-ebs-csi"
  attach_ebs_csi_policy = true
  oidc_providers = {
    main = { provider_arn = module.eks.oidc_provider_arn, namespace_service_accounts = ["kube-system:ebs-csi-controller-sa"] }
  }
}

resource "aws_ecr_repository" "app" {
  name                 = var.name
  image_tag_mutability = "IMMUTABLE"
  force_delete         = true
  image_scanning_configuration { scan_on_push = true }
}

resource "aws_ecr_lifecycle_policy" "app" {
  repository = aws_ecr_repository.app.name
  policy = jsonencode({ rules = [{
    rulePriority = 1, description = "Keep last 10 images",
    selection = { tagStatus = "any", countType = "imageCountMoreThan", countNumber = 10 },
    action = { type = "expire" }
  }] })
}

output "ecr_url"      { value = aws_ecr_repository.app.repository_url }
output "cluster_name" { value = module.eks.cluster_name }
