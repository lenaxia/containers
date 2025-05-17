FROM debian:bullseye-slim

USER root

# Install required packages
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        catatonit \
        mysql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy the entrypoint script and initdb directory
COPY entrypoint.sh /entrypoint.sh
COPY initdb /initdb

# Make the script executable and ensure proper permissions
RUN chmod +x /entrypoint.sh && \
    mkdir -p /initdb && \
    chown -R nobody:nogroup /initdb && \
    chmod -R 755 /initdb

USER nobody:nogroup
ENTRYPOINT ["/usr/bin/catatonit", "--"]
CMD ["/entrypoint.sh"]
