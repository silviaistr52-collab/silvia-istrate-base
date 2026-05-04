import logging
import os
import uuid

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from log_analytics.core import analyze
from log_analytics.sources import read_s3_prefix

# Read the git SHA from an env var. The Dockerfile bakes this in at build
# time via a build arg, so /version returns whatever was deployed. Defaults
# to "unknown" for local development where we haven't set it.
GIT_SHA = os.environ.get("GIT_SHA", "unknown")


# Configure structured JSON logging — easier to query in CloudWatch.
# We could use a library for this but stdlib is fine for the take-home.
logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s","level":"%(levelname)s","msg":"%(message)s"}',
)
logger = logging.getLogger("log_analytics")


# Create the FastAPI app instance. Uvicorn (the server) imports this object
# by name when starting up — see the CMD line in the Dockerfile later.
app = FastAPI(
    title="Log Analytics Service",
    version="0.1.0",
)


# Middleware runs before every request. We use it to attach a unique request
# ID and log each request with that ID. Standard observability pattern.
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = str(uuid.uuid4())
    logger.info(f"request_id={request_id} method={request.method} path={request.url.path}")

    response = await call_next(request)

    response.headers["x-request-id"] = request_id
    return response


@app.get("/healthz")
def healthz():
    """Liveness probe — does the process work at all?

    Must NOT depend on external services. If S3 is down, the process is
    still alive and the platform shouldn't restart it. /readyz handles
    the dependency check.
    """
    return {"status": "ok"}


@app.get("/readyz")
def readyz():
    """Readiness probe — can I serve real traffic?

    We do a cheap S3 call (list buckets) to confirm we have credentials
    and S3 is reachable. If this fails, the load balancer should stop
    sending us traffic until it recovers.
    """
    try:
        boto3.client("s3").list_buckets()
        return {"status": "ready"}
    except (BotoCoreError, ClientError) as e:
        logger.warning(f"readyz failed: {e}")
        # 503 Service Unavailable — standard signal to the load balancer
        # to stop routing traffic here.
        raise HTTPException(status_code=503, detail="dependencies unavailable") from e


@app.get("/version")
def version():
    """Return the git SHA the container was built from.

    Used to verify CI/CD actually deployed what you think it did.
    """
    return {"version": GIT_SHA}


@app.get("/analyze")
def analyze_endpoint(
    bucket: str = Query(..., description="S3 bucket name"),
    prefix: str = Query("", description="S3 key prefix"),
    threshold: int = Query(10, description="Alert threshold"),
):
    """Run the analyser against an S3 prefix.

    Returns the same JSON shape the CLI produces. Errors return a clean
    JSON envelope with an appropriate HTTP status — no stack traces.
    """
    try:
        lines = read_s3_prefix(bucket, prefix)
        result = analyze(lines, threshold)
        return result
    except (BotoCoreError, ClientError) as e:
        logger.error(f"S3 error: {e}")
        raise HTTPException(status_code=502, detail="upstream S3 error") from e
    except Exception:
        logger.exception("unexpected error")
        raise HTTPException(status_code=500, detail="internal server error") from None


# Custom exception handler — ensures every error response is consistent JSON,
# never a stack trace. Spec section 1.4: "Don't leak stack traces."
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail},
    )
