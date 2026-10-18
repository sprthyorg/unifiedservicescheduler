# syntax=docker/dockerfile:1.7
# Test-runner image: everything needed to run every test suite inside Docker (no host Python).
# Build context = repository root (contract tests read 04-design/, smoke test lives in deploy/).
FROM python:3.12-slim
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
WORKDIR /repo/services/scheduler-service
COPY services/scheduler-service/requirements.txt services/scheduler-service/requirements-dev.txt ./
RUN pip install -r requirements-dev.txt
COPY 04-design /repo/04-design
COPY deploy/local-smoke-test.sh deploy/docker/run-tests.sh /repo/deploy/
COPY services/scheduler-service /repo/services/scheduler-service
ENTRYPOINT ["bash", "/repo/deploy/run-tests.sh"]
