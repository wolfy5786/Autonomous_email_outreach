terraform {
  backend "s3" {
    bucket         = "email-outreach-tfstate"
    key            = "terraform.tfstate"
    region         = "us-west-2"
    dynamodb_table = "email-outreach-tf-lock"
    encrypt        = true
  }
}
