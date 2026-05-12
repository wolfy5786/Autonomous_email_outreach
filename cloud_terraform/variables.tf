variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-west-2"
}

variable "environment" {
  description = "Environment name (dev, prod)"
  type        = string
  default     = "dev"
}

variable "cluster_name" {
  description = "EKS cluster name"
  type        = string
  default     = "email-outreach-dev"
}

variable "vpc_cidr" {
  description = "VPC CIDR block"
  type        = string
  default     = "10.40.0.0/16"
}

variable "services" {
  description = "List of application services for ECR repos and IRSA roles"
  type        = list(string)
  default     = ["orchestrator", "planning", "sourcing", "prospecting", "messaging", "web-ui"]
}
