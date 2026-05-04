# silvia-istrate-base

A note on the submission: the Python files contain more inline comments than you would typically see in production code. This was intentional — I found the Python side of the assignment more challenging than expected, and I used AI assistance to help implement it. The comments reflect my own effort to understand what the code does rather than just ship it blind.


# Log Analytics Service

A streaming log analytics service that reads JSONL error logs from S3 and produces a summary. Exposed as both a CLI tool and an HTTP API, deployed on AWS ECS Fargate behind CloudFront.

**Live endpoint:** https://d1w9xlnbvjdnua.cloudfront.net

---

## How do I run it locally against a local file?

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install uv && uv pip install -e ".[dev]"
analyze --file samples/sample.jsonl --threshold 3
```

Exit codes: `0` = success, `2` = alert fired, `1` = error.

To run against S3:

```bash
analyze --bucket devops-assignment-logs-april --threshold 5
```

To run the HTTP API locally:

```bash
uvicorn log_analytics.api:app --host 0.0.0.0 --port 8000
curl "http://localhost:8000/analyze?bucket=devops-assignment-logs-april&threshold=5"
```

---

## How do I run the tests?

```bash
# Fast unit tests
pytest -m "not slow" -v

# Full suite including streaming memory assertion (~40 seconds)
pytest -v
```

The streaming test generates 500,000 log lines in memory and asserts that peak Python-allocated memory stays under 10MB — proving the analyser never buffers the input regardless of size.

---

## What would break first if traffic increased 100x?

The bottleneck is **S3 read latency and cost**, not the ECS service.

Every `/analyze` request re-reads all objects under the prefix from S3. At current traffic that is fine — five small files, fast response. At 100x traffic, two things happen:

1. **S3 GET request costs and latency multiply linearly.** Each request reads the same data. At high enough volume, you are paying for the same bytes repeatedly.
2. **The single ECS task becomes a bottleneck.** At `desired_count=1`, requests queue behind each other. Each S3 read takes hundreds of milliseconds; concurrent requests stack up.

What I would do:

- **Cache analysis results** keyed by `(bucket, prefix, threshold)` with a short TTL. CloudFront already caches `/analyze` for 60 seconds — repeated identical queries serve from the edge with zero S3 reads.
- **Scale ECS horizontally** — increase `desired_count` and let the ALB distribute load. The service is stateless so this is straightforward.
- **Pre-compute summaries on S3 event triggers** — an S3 `ObjectCreated` event triggers a Lambda that updates a DynamoDB summary. The API reads from DynamoDB instead of re-scanning S3. Eliminates per-request S3 reads entirely for the sustained high-traffic case.

---

## What did I cut or skip, and why?

**HTTPS on the ALB.** CloudFront terminates TLS and talks to the ALB over HTTP internally. Without a custom domain there is no certificate to attach to the ALB. In production I would use ACM to provision a certificate, attach a custom domain, and enforce HTTPS end-to-end.

**A custom VPC.** The service deploys into the default VPC using its existing public subnets. For a production service I would build a dedicated VPC with private subnets for the ECS tasks, a NAT gateway for egress, and no public IPs on the tasks. The default VPC was the right call for a single-service take-home in a fresh account.

**`test_sources.py` and `test_api.py`.** The spec asks for unit tests on the core analysis logic and a streaming proof — both present. Integration tests for the S3 adapter (using moto) and the FastAPI endpoints (using TestClient) would be the next thing I would add. Cut for time.

**The `--since` flag.** The optional stretch goal for filtering logs by time window. The data model supports it (every record has a `ts` field) but it was not called out as required and the time was better spent on the infrastructure and streaming proof.

**Ports and adapters as a formal pattern.** The code has the spirit of hexagonal architecture — the analyser takes an iterator of strings and does not know or care about the source — but I did not formalise it with explicit Protocol classes. Given the time budget, implicit is good enough and the code is easier to read for it.

**Single repo for app and infra.** In production I would split them — different change cadences, different reviewers, different deploy permissions. For a take-home, one repo with two workflow jobs is simpler to review.

---

## Architecture

```
GitHub Actions (push to main)
    │
    ├── build Docker image → push to ECR
    └── terraform apply
            │
            ▼
    CloudFront (https://d1w9xlnbvjdnua.cloudfront.net)
            │
            ▼
    ALB (HTTP:80)
            │
            ▼
    ECS Fargate (256 CPU / 512 MB)
            │
            ▼
    S3 (devops-assignment-logs-april) ← streaming, line by line
```

**IAM:** the ECS task role has only `s3:ListBucket` on the logs bucket, `s3:GetObject` on its objects, and `s3:ListAllMyBuckets` for the `/readyz` health check. No `s3:*` on `*`.

**CI/CD:** GitHub Actions authenticates to AWS via OIDC federation — no long-lived credentials stored in GitHub Secrets.

---

## Endpoints

| Endpoint | Description |
|---|---|
| `GET /analyze?bucket=&prefix=&threshold=` | Run analysis against S3 prefix |
| `GET /healthz` | Liveness probe — no dependencies |
| `GET /readyz` | Readiness probe — verifies S3 reachable |
| `GET /version` | Git SHA the container was built from |

---

## Deploying

```bash
# Bootstrap (one-time)
aws s3 mb s3://bmc-candidate-tf-state-206453958024 --region eu-north-1
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1
cd infra && terraform init
terraform apply -target=aws_iam_role.github_actions -target=aws_iam_role_policy.github_actions

# After that, every push to main deploys automatically via GitHub Actions
git push origin main
```

## Sample log format

```json
{"ts":"2025-09-15T14:10:04Z","service":"api","level":"ERROR","msg":"500 internal server error","endpoint":"/checkout","latency_ms":2001}
```

Each line is a JSON object with at least `ts`, `service`, `level`, and `msg`. Extra fields are ignored. Lines with `level != "ERROR"` are skipped. Malformed lines are counted in `parseErrors` and skipped without crashing.
