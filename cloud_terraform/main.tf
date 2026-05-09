# ── Network ───────────────────────────────────────────────────────
module "network" {
  source      = "./modules/network"
  environment = var.environment
  vpc_cidr    = var.vpc_cidr
  aws_region  = var.aws_region
}

# ── EKS Cluster ──────────────────────────────────────────────────
module "eks" {
  source       = "./modules/eks"
  environment  = var.environment
  cluster_name = var.cluster_name
  vpc_id       = module.network.vpc_id
  subnet_ids   = module.network.private_subnet_ids
}

# ── Node Groups ──────────────────────────────────────────────────
module "node_groups" {
  source       = "./modules/node-groups"
  cluster_name = module.eks.cluster_name
  subnet_ids   = module.network.private_subnet_ids
  environment  = var.environment
}

# ── Karpenter Autoscaler ─────────────────────────────────────────
module "karpenter" {
  source       = "./modules/karpenter"
  cluster_name = module.eks.cluster_name
  oidc_issuer  = module.eks.oidc_issuer
}

# ── ECR Repositories ─────────────────────────────────────────────
module "ecr" {
  source   = "./modules/ecr"
  services = var.services
}

# ── RabbitMQ (optional — Amazon MQ) ──────────────────────────────
module "rabbitmq" {
  source      = "./modules/rabbitmq"
  environment = var.environment
  vpc_id      = module.network.vpc_id
  subnet_ids  = module.network.private_subnet_ids
}

# ── Secrets Manager ──────────────────────────────────────────────
module "secrets" {
  source      = "./modules/secrets"
  environment = var.environment
}

# ── IAM IRSA Roles ───────────────────────────────────────────────
module "iam_irsa" {
  source       = "./modules/iam-irsa"
  cluster_name = module.eks.cluster_name
  oidc_issuer  = module.eks.oidc_issuer
  services     = var.services
}

# ── S3 Backup Bucket ─────────────────────────────────────────────
module "s3_backup" {
  source      = "./modules/s3-backup"
  environment = var.environment
}

# ── Observability ─────────────────────────────────────────────────
module "observability" {
  source      = "./modules/observability"
  environment = var.environment
  cluster_name = var.cluster_name
}

# ── Route53 (optional) ───────────────────────────────────────────
module "route53" {
  source      = "./modules/route53"
  environment = var.environment
}
