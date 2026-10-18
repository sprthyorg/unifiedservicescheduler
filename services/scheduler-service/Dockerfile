# syntax=docker/dockerfile:1.7
# ---- build stage: install dependencies into a virtualenv -------------------
FROM python:3.12-slim AS build
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt .
RUN pip install -r requirements.txt

# ---- runtime stage: slim, non-root, read-only friendly -------------------
FROM python:3.12-slim AS runtime
ARG VERSION=1.0.0
LABEL org.opencontainers.image.title="scheduler-service" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.description="Unified Service Scheduler API"
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PATH="/opt/venv/bin:$PATH"
RUN groupadd --system app && useradd --system --gid app --uid 10001 app
WORKDIR /srv
COPY --from=build /opt/venv /opt/venv
COPY app ./app
COPY migrations ./migrations
USER 10001
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=2s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health/live',timeout=2).status==200 else 1)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--no-server-header"]
