# Dockerfile — builds the log-analytics service container
#
# Multi-stage build:
#   Stage 1 (builder) — installs dependencies into a clean layer
#   Stage 2 (runtime) — copies only what's needed to run, no build tools
#
# Why multi-stage? The final image is smaller and has a smaller attack
# surface — no pip, no compiler, no build-time tools in production.

# ── Stage 1: builder ────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# Copy only the files pip needs to install dependencies.
# We copy these before the source code so Docker can cache this layer —
# if only the source changes (not pyproject.toml), pip doesn't re-run.
COPY pyproject.toml ./
COPY src/ ./src/

# Install the package and its runtime dependencies into a local directory.
# --no-cache-dir keeps the layer small.
# We install into /install so we can copy just that into the runtime stage.
RUN pip install --no-cache-dir --prefix=/install .


# ── Stage 2: runtime ────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# GIT_SHA is passed in at build time by CI/CD:
#   docker build --build-arg GIT_SHA=$(git rev-parse --short HEAD) .
# The /version endpoint reads this env var and returns it, which lets
# you confirm the right commit was deployed.
ARG GIT_SHA=unknown
ENV GIT_SHA=${GIT_SHA}

# Run as a non-root user. Running containers as root is a security
# risk — if the container is compromised, the attacker gets root inside
# the container. A dedicated user limits the blast radius.
RUN useradd --no-create-home --shell /bin/false appuser

WORKDIR /app

# Copy the installed packages from the builder stage.
COPY --from=builder /install /usr/local

# Copy the source code.
COPY src/ ./src/

# Switch to the non-root user before starting the process.
USER appuser

# Expose the port uvicorn listens on. This is documentation — it doesn't
# actually publish the port (that's done by ECS task definition / docker run -p).
EXPOSE 8000

# Start the FastAPI app via uvicorn.
# --host 0.0.0.0 listens on all interfaces (required in a container).
# --port 8000 matches the ECS task definition and target group.
# --workers 1 keeps memory within the 256MB limit the spec sets.
# --no-access-log reduces noise — we have structured request logging in the app.
CMD ["uvicorn", "log_analytics.api:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1", \
     "--no-access-log"]