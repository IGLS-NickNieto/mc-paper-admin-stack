ARG OLIVETIN_BASE_IMAGE=bnhf/olivetin:2026.05.24
FROM ${OLIVETIN_BASE_IMAGE}

USER root

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
      argon2 \
      bash \
      ca-certificates \
      curl \
      docker.io \
      docker-compose \
      gettext-base \
      jq \
      mariadb-client \
      openssl \
    && rm -rf /var/lib/apt/lists/*

COPY images/olivetin/docker-wrapper.sh /usr/local/bin/docker
RUN chmod +x /usr/local/bin/docker

WORKDIR /workspace

ENTRYPOINT ["/bin/bash", "/workspace/scripts/entrypoint-olivetin.sh"]
