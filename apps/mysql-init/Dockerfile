# syntax=docker/dockerfile:1

FROM docker.io/library/alpine:3.22
ARG VERSION

USER root

RUN \
    apk add --no-cache \
        bash \
        ca-certificates \
        catatonit \
        mysql-client \
    && rm -rf /tmp/*

COPY entrypoint.sh /entrypoint.sh
COPY initdb /initdb

RUN chmod +x /entrypoint.sh && \
    mkdir -p /initdb && \
    chown -R nobody:nogroup /initdb && \
    chmod -R 755 /initdb

USER nobody:nogroup
ENTRYPOINT ["/usr/bin/catatonit", "--"]
CMD ["/entrypoint.sh"]
