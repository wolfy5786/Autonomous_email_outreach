FROM node:20-alpine AS builder

WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY tsconfig.json ./
COPY config/ ./config/
COPY types/ ./types/
COPY models/ ./models/
COPY services/ ./services/
COPY routes/ ./routes/
COPY middleware/ ./middleware/
COPY main.ts app.ts ./
COPY ../local_infrastructure/ ../local_infrastructure/
RUN npx tsc

FROM node:20-alpine

WORKDIR /app
COPY package*.json ./
RUN npm ci --production
COPY --from=builder /app/dist ./dist

ENV NODE_ENV=production
EXPOSE 3000

CMD ["node", "dist/orchestrator/main.js"]
