# syntax=docker/dockerfile:1.7

# ── builder ──────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /build

# Layer caching: copy lockfile-relevant files first.
COPY web-ui/package.json web-ui/package-lock.json* ./
RUN npm install --no-audit --no-fund

# Now copy sources and build.
COPY web-ui/ ./
# Bake the gateway URL into the bundle at build time. Default is empty, which
# means the app talks to /api on the same origin (handled by nginx below).
ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

# ── runtime ──────────────────────────────────────────────
FROM nginx:1.27-alpine

# nginx config that serves the SPA and proxies /api/* to the gateway service
# (override the upstream via the GATEWAY_URL env at run time if needed).
COPY web-ui/nginx.conf /etc/nginx/templates/default.conf.template
COPY --from=builder /build/dist /usr/share/nginx/html

ENV GATEWAY_URL="http://gateway:8000"
EXPOSE 8082

CMD ["nginx", "-g", "daemon off;"]
