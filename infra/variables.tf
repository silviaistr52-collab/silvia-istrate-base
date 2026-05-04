variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "eu-north-1"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "app_name" {
  description = "Application name — used to name resources consistently"
  type        = string
  default     = "log-analytics"
}

variable "logs_bucket" {
  description = "S3 bucket containing the JSONL log files to analyse"
  type        = string
  default     = "devops-assignment-logs-april"
}

variable "container_port" {
  description = "Port the container listens on"
  type        = number
  default     = 8000
}

variable "task_cpu" {
  description = "ECS task CPU units (1 vCPU = 1024)"
  type        = number
  default     = 256
}

variable "task_memory" {
  description = "ECS task memory in MB. Must be <= 256 per the spec."
  type        = number
  default     = 512
}

variable "desired_count" {
  description = "Number of ECS tasks to run"
  type        = number
  default     = 1
}

variable "image_tag" {
  description = "Docker image tag to deploy. Set by CI/CD to the git SHA."
  type        = string
  default     = "latest"
}