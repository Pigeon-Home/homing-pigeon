FROM python:3.14-slim

LABEL org.opencontainers.image.source="https://github.com/Pigeon-Home/homing-pigeon"
LABEL org.opencontainers.image.description="Homing Pigeon runner — email-driven agent execution"
LABEL org.opencontainers.image.licenses="Apache-2.0"

# Non-root user: the runner never needs root inside the container.
RUN useradd --create-home --shell /bin/bash pigeon

WORKDIR /app

# Runner is stdlib-only — no pip install needed.
COPY runner/ ./runner/
COPY .github/docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh && chown -R pigeon:pigeon /app /entrypoint.sh

# State directory for seen.json and job workdirs. Mount a volume here
# to survive container restarts.
RUN mkdir -p /data && chown pigeon:pigeon /data
VOLUME /data

USER pigeon

# No ports: the runner polls outbound (IMAP) and sends outbound (SMTP).
# Nothing listens.

ENTRYPOINT ["/entrypoint.sh"]
CMD ["--config", "/data/config.json"]
