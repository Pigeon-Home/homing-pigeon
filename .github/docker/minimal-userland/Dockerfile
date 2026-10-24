# Agent-Stamp: 30000f1a-3b4c-4d5e-8f6a-7b8c9d0e1f2a
#
# A bare-bones box for runner/tests/test_minimal_userland.py: Alpine, so
# /bin/sh is BusyBox ash and bash is not installed. The repair
# tests need exactly that absence. This image is a test fixture,
# not a release artifact; the published image is ../Dockerfile.
#
#   docker build -f .github/docker/minimal-userland/Dockerfile -t hp-minimal .
#   docker run --rm hp-minimal
FROM python:3.12-alpine

# Fail the build, not the tests, if the base image ever grows bash.
RUN ! command -v bash && ! command -v zsh \
    && [ "$(readlink -f /bin/sh)" = /bin/busybox ]

RUN adduser -D pigeon
WORKDIR /app
# runner/ carries the suite (runner/tests/).
COPY runner/ ./runner/
RUN chown -R pigeon:pigeon /app
USER pigeon

ENV HP_MINIMAL_USERLAND=1 PYTHONDONTWRITEBYTECODE=1
CMD ["python3", "-m", "unittest", "runner.tests.test_minimal_userland", "-v"]
