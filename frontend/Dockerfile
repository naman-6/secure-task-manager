# =============================================================================
# Stage 1: Builder - installs node_modules and produces the static build
# =============================================================================
FROM node:20-alpine AS builder

WORKDIR /build

COPY package.json ./
RUN npm install --no-audit --no-fund

COPY vite.config.js index.html ./
COPY src ./src

RUN npm run build

# =============================================================================
# Stage 2: Runtime - minimal nginx image, non-root, no build tools
# =============================================================================
FROM nginxinc/nginx-unprivileged:1.27-alpine AS runtime

LABEL maintainer="devsecops-mothership" \
      description="Secure Task & Asset Manager - Frontend"

# nginxinc/nginx-unprivileged already creates and runs as a non-root
# "nginx" user (uid 101) and listens on unprivileged ports by default.
USER root

# Remove default content and replace with our custom config/build output.
RUN rm -rf /usr/share/nginx/html/* /etc/nginx/conf.d/default.conf

COPY nginx.conf /etc/nginx/nginx.conf
COPY --from=builder /build/dist /usr/share/nginx/html

# Ensure the nginx user owns everything it needs to write to at runtime,
# since the container will run with readOnlyRootFilesystem: true and only
# /tmp and /var/cache/nginx mounted as writable emptyDir volumes.
RUN mkdir -p /var/cache/nginx /tmp \
    && chown -R 101:101 /usr/share/nginx/html /var/cache/nginx /etc/nginx /tmp

USER 101

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://127.0.0.1:8080/healthz || exit 1

ENTRYPOINT ["nginx", "-g", "daemon off;"]
