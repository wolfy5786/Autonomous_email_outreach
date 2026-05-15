# S3 backend commented out for demo — state stored in terraform.tfstate locally.
# Uncomment and create the bucket/table when moving to a persistent setup.
# terraform {
#   backend "s3" {
#     bucket       = "email-outreach-tfstate"
#     key          = "terraform.tfstate"
#     region       = "us-west-2"
#     use_lockfile = true
#     encrypt      = true
#   }
# }
