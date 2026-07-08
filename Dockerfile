FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /uvx /bin/

# Keep the venv outside /app so a bind-mounted working copy doesn't shadow it
ENV UV_PROJECT_ENVIRONMENT=/opt/venv UV_COMPILE_BYTECODE=1
WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY hadr/ hadr/
COPY agent/ agent/
COPY ops/ ops/

# supercronic powers the optional VPS heartbeat profile (compose --profile heartbeat)
ADD --chmod=755 https://github.com/aptible/supercronic/releases/download/v0.2.33/supercronic-linux-amd64 /usr/local/bin/supercronic

ENTRYPOINT ["/opt/venv/bin/python"]
CMD ["-m", "agent.morning"]
