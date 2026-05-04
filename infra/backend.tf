terraform {
  backend "s3" {
    bucket  = "bmc-candidate-tf-state-206453958024"
    key     = "log-analytics/terraform.tfstate"
    region  = "eu-north-1"
    encrypt = true
  }
}