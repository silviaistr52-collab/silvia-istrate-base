# We don't cache /healthz, /readyz, or /version — those must always
# hit the origin. We only cache /analyze since log data doesn't change
# frequently.

resource "aws_cloudfront_distribution" "app" {
  enabled         = true
  is_ipv6_enabled = true
  comment         = "${var.app_name} distribution"

  origin {
    domain_name = aws_lb.app.dns_name
    origin_id   = "alb"

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "http-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  # Default cache behaviour — applies to all paths not matched below.
  # We disable caching for most paths so health checks and version
  # always return live data.
  default_cache_behavior {
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "alb"
    viewer_protocol_policy = "redirect-to-https"
    compress               = true

    forwarded_values {
      query_string = true
      cookies {
        forward = "none"
      }
    }

    # TTL of 0 means CloudFront always goes to the origin.
    min_ttl     = 0
    default_ttl = 0
    max_ttl     = 0
  }

  # Cache behaviour for /analyze — cache for 60 seconds.
  # Same query string = same result, so caching is safe here.
  ordered_cache_behavior {
    path_pattern           = "/analyze"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "alb"
    viewer_protocol_policy = "redirect-to-https"
    compress               = true

    forwarded_values {
      # Forward query strings so bucket/prefix/threshold are part of
      # the cache key — different params = different cached response.
      query_string = true
      cookies {
        forward = "none"
      }
    }

    min_ttl     = 0
    default_ttl = 60
    max_ttl     = 300
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }
}