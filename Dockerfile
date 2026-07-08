FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /uvx /bin/

# Keep the venv outside /app so a bind-mounted working copy doesn't shadow it
ENV UV_PROJECT_ENVIRONMENT=/opt/venv UV_COMPILE_BYTECODE=1
WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY hadr/ hadr/

ENTRYPOINT ["/opt/venv/bin/python", "-m", "hadr"]
CMD ["--feeds", "usgs"]
