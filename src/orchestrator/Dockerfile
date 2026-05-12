# syntax=docker/dockerfile:1.7

# Build context MUST be ./src — orchestrator's tsconfig has rootDir: ".."
# and imports from "../local_infrastructure/rabbit_mq/broker.interface".

# ── builder ──────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

# Install deps for caching.
COPY orchestrator/package*.json orchestrator/
RUN cd orchestrator && npm ci

# Sources orchestrator needs at compile time.
# tsconfig has rootDir: ".." and include: ["../local_infrastructure/**/*", "../shared/**/*"]
COPY orchestrator/ orchestrator/
COPY local_infrastructure/ local_infrastructure/
COPY shared/ shared/

# Run tsc — orchestrator/tsconfig has outDir: "./dist" and rootDir: "..",
# so output lands at /app/orchestrator/dist/orchestrator/main.js
RUN cd orchestrator && npx tsc

# ── runtime ──────────────────────────────────────────────
FROM node:20-alpine

WORKDIR /app

COPY orchestrator/package*.json ./
RUN npm ci --omit=dev

COPY --from=builder /app/orchestrator/dist ./dist

ENV NODE_ENV=production \
    PORT=3000
EXPOSE 3000

CMD ["node", "dist/orchestrator/main.js"]
