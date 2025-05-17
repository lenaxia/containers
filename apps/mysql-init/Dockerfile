FROM debian:bullseye-slim

ARG VERSION
USER root

# Install required packages
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        catatonit \
        mysql-client="${VERSION}" \
    && rm -rf /var/lib/apt/lists/*

# Copy the entrypoint script
COPY ./apps/mysql-init/entrypoint.sh /entrypoint.sh
COPY ./initdb /initdb

# Make the script executable
RUN chmod +x /entrypoint.sh && \
    mkdir -p /initdb && \
    chown nobody:nogroup /initdb

USER nobody:nogroup
ENTRYPOINT ["/usr/bin/catatonit", "--"]
CMD ["/entrypoint.sh"]
