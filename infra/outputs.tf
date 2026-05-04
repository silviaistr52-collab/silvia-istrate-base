output "ecr_repository_url" {
  description = "ECR repository URL for docker push"
  value       = aws_ecr_repository.app.repository_url
}

output "cloudfront_url" {
  description = "CloudFront distribution URL — the public endpoint"
  value       = "https://${aws_cloudfront_distribution.app.domain_name}"
}

output "cloudfront_domain" {
  description = "CloudFront domain name (without https://)"
  value       = aws_cloudfront_distribution.app.domain_name
}

output "ecs_cluster_name" {
  description = "ECS cluster name — used by CI/CD to force new deployment"
  value       = aws_ecs_cluster.app.name
}

output "ecs_service_name" {
  description = "ECS service name — used by CI/CD to force new deployment"
  value       = aws_ecs_service.app.name
}