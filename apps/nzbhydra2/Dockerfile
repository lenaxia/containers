# syntax=docker/dockerfile:1

FROM docker.io/library/eclipse-temurin:17-jre-alpine-3.22
ARG VERSION

USER root
WORKDIR /app

RUN \
    wget -q "https://github.com/theotherp/nzbhydra2/releases/download/v${VERSION}/nzbhydra2-${VERSION}-generic.zip" -O /tmp/nzbhydra2.zip \
    && unzip -oq /tmp/nzbhydra2.zip 'lib/*' -d /app \
    && mv /app/lib/core-*-exec.jar /app/nzbhydra2.jar \
    && rm -rf /tmp/* /app/lib \
    && mkdir -p /config \
    && chown nobody:nogroup /config \
    && chmod 775 /config \
    && chown -R root:root /app \
    && chmod -R 755 /app

USER nobody:nogroup
WORKDIR /config
VOLUME ["/config"]
EXPOSE 5076

ENTRYPOINT ["java", "-XX:MaxRAMPercentage=75.0", "-Dsun.security.pkcs11.enable-solaris=false", "-Dfile.encoding=UTF8", "-jar", "/app/nzbhydra2.jar", "--nobrowser", "--datafolder", "/config", "directstart"]
