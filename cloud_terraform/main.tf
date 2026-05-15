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

# ── ECR Repositories ─────────────────────────────────────────────
module "ecr" {
  source   = "./modules/ecr"
  services = var.services
}

# ── Disabled for demo (stubs / not needed) ───────────────────────
# module "karpenter"   { ... }  # auto-scaling — overkill for demo
# module "rabbitmq"    { ... }  # use in-cluster RabbitMQ instead
# module "secrets"     { ... }  # use kubectl create secret instead
# module "iam_irsa"    { ... }  # not needed for demo
# module "s3_backup"   { ... }  # not needed for demo
# module "observability" { ... } # install via Helm after cluster is up
# module "route53"     { ... }  # use LoadBalancer URL instead
