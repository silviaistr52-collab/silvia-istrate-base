terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  # Tags applied to every resource in this provider block.
  # Saves repeating tags on every resource individually.
  default_tags {
    tags = {
      Project     = "log-analytics"
      Environment = var.environment
      ManagedBy   = "terraform"
      Candidate   = "silvia-istrate"
    }
  }
}
