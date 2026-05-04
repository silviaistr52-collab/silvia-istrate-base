resource "aws_ecs_cluster" "app" {
  name = var.app_name

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

# CloudWatch log group for container logs.
resource "aws_cloudwatch_log_group" "app" {
  name              = "/ecs/${var.app_name}"
  retention_in_days = 7
}

resource "aws_ecs_task_definition" "app" {
  family                   = var.app_name
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.task_cpu
  memory                   = var.task_memory

  # The execution role lets ECS pull the image and write logs.
  execution_role_arn = aws_iam_role.ecs_execution.arn
  task_role_arn      = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name  = var.app_name
    image = "${aws_ecr_repository.app.repository_url}:${var.image_tag}"

    portMappings = [{
      containerPort = var.container_port
      protocol      = "tcp"
    }]

    environment = [
      {
        # GIT_SHA is baked into the image at build time (see Dockerfile).
        # The /version endpoint reads this env var and returns it.
        # We also set it here as a fallback so it's visible in ECS console.
        name  = "GIT_SHA"
        value = var.image_tag
      },
      {
        name  = "AWS_DEFAULT_REGION"
        value = var.aws_region
      }
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.app.name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "ecs"
      }
    }

    # Healthcheck at the container level — ECS uses this to know if
    # the container is ready before registering it with the target group.
    healthCheck = {
      command     = ["CMD-SHELL", "curl -f http://localhost:${var.container_port}/healthz || exit 1"]
      interval    = 30
      timeout     = 5
      retries     = 3
      startPeriod = 10
    }
  }])
}

resource "aws_ecs_service" "app" {
  name            = var.app_name
  cluster         = aws_ecs_cluster.app.id
  task_definition = aws_ecs_task_definition.app.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  # Force a new deployment when the task definition changes.
  # Without this, updating the image tag wouldn't trigger a rollout.
  force_new_deployment = true

  network_configuration {
    subnets          = data.aws_subnets.public.ids
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.app.arn
    container_name   = var.app_name
    container_port   = var.container_port
  }

  depends_on = [
    aws_lb_listener.http,
    aws_iam_role_policy_attachment.ecs_execution,
  ]
}