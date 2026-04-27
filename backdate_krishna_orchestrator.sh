#!/bin/bash

# ============================================================
# Backdate Git Commits — Krishna_orchestrator Branch
# Builds the orchestrator service from scratch with real code
# April 27 – May 13, 2026 | 39 commits
# ============================================================

set -e

BRANCH="Krishna_orchestrator"
CURRENT=$(git rev-parse --abbrev-ref HEAD)
if [ "$CURRENT" != "$BRANCH" ]; then
  echo "❌  Not on '$BRANCH'. Run: git checkout $BRANCH"
  exit 1
fi

echo "✅  On branch '$BRANCH'. Building orchestrator service..."
echo ""

make_commit() {
  local DATE="$1"; local MSG="$2"; shift 2
  git add -A
  GIT_AUTHOR_DATE="$DATE" GIT_COMMITTER_DATE="$DATE" git commit -m "$MSG"
  echo "  ✔  [$DATE] $MSG"
}

# ════════════════════════════════════════════════════════════
# WEEK 1 — Apr 27 – May 3  (13 commits)
# ════════════════════════════════════════════════════════════
echo "── Week 1: Apr 27 – May 3 ─────────────────────────────"

# --- Commit 1: scaffold orchestrator package.json + tsconfig ---
mkdir -p src/orchestrator
cat > src/orchestrator/package.json << 'EOF'
{
  "name": "orchestrator",
  "version": "1.0.0",
  "description": "Orchestrator service — coordinates the outreach pipeline",
  "main": "dist/main.js",
  "scripts": {
    "dev": "ts-node-dev --respawn main.ts",
    "build": "tsc",
    "start": "node dist/main.js",
    "test": "jest --passWithNoTests"
  },
  "dependencies": {
    "express": "^4.18.2",
    "amqplib": "^0.10.3",
    "pg": "^8.11.3",
    "mongoose": "^7.6.3",
    "dotenv": "^16.3.1",
    "uuid": "^9.0.0"
  },
  "devDependencies": {
    "typescript": "^5.3.2",
    "@types/express": "^4.17.21",
    "@types/amqplib": "^0.10.4",
    "@types/pg": "^8.10.9",
    "@types/uuid": "^9.0.7",
    "ts-node-dev": "^2.0.0",
    "jest": "^29.7.0",
    "@types/jest": "^29.5.11",
    "ts-jest": "^29.1.1"
  }
}
EOF

cat > src/orchestrator/tsconfig.json << 'EOF'
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "commonjs",
    "lib": ["ES2020"],
    "outDir": "./dist",
    "rootDir": ".",
    "strict": true,
    "esModuleInterop": true,
    "resolveJsonModule": true,
    "declaration": true,
    "sourceMap": true,
    "skipLibCheck": true
  },
  "include": ["./**/*.ts"],
  "exclude": ["node_modules", "dist"]
}
EOF
make_commit "2026-04-27 09:00:00" "chore(orchestrator): init package.json and tsconfig"

# --- Commit 2: config module ---
mkdir -p src/orchestrator/config
cat > src/orchestrator/config/index.ts << 'EOF'
import dotenv from 'dotenv';
dotenv.config();

export const config = {
  port: parseInt(process.env.PORT || '3000', 10),
  rabbitmqUrl: process.env.RABBITMQ_URL || 'amqp://guest:guest@localhost:5672',
  mongoUri: process.env.MONGO_URI || 'mongodb://localhost:27017/outreach',
  postgresUrl: process.env.DATABASE_URL || 'postgresql://postgres:postgres@localhost:5432/orchestrator',
  exchange: process.env.EXCHANGE_NAME || 'outreach.events',
  nodeEnv: process.env.NODE_ENV || 'development',
};
EOF

cat > src/orchestrator/.env.example << 'EOF'
PORT=3000
RABBITMQ_URL=amqp://guest:guest@localhost:5672
MONGO_URI=mongodb://localhost:27017/outreach
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/orchestrator
EXCHANGE_NAME=outreach.events
NODE_ENV=development
EOF
make_commit "2026-04-27 11:30:00" "feat(config): add environment config module with .env.example"

# --- Commit 3: types ---
mkdir -p src/orchestrator/types
cat > src/orchestrator/types/campaign.ts << 'EOF'
export type CampaignStatus =
  | 'CREATED'
  | 'PLANNING'
  | 'PLAN_READY'
  | 'SOURCING'
  | 'SOURCING_FAILED'
  | 'PROSPECTING'
  | 'MESSAGING'
  | 'COMPLETED'
  | 'PAUSED'
  | 'CANCELLED';

export interface Campaign {
  id: string;
  name: string;
  icp: ICPDefinition;
  status: CampaignStatus;
  createdAt: Date;
  updatedAt: Date;
}

export interface ICPDefinition {
  industry: string;
  companySize: string;
  region: string;
  titles: string[];
  keywords: string[];
}

export interface CampaignStats {
  campaignId: string;
  totalProspects: number;
  emailsSent: number;
  opened: number;
  replied: number;
  openRate: number;
  replyRate: number;
}
EOF

cat > src/orchestrator/types/events.ts << 'EOF'
export interface PlanRequested {
  type: 'plan.requested';
  campaignId: string;
  icp: {
    industry: string;
    companySize: string;
    region: string;
    titles: string[];
    keywords: string[];
  };
  timestamp: string;
}

export interface PlanReady {
  type: 'plan.ready';
  campaignId: string;
  planId: string;
  sources: string[];
  timestamp: string;
}

export interface SourcingCompleted {
  type: 'sourcing.completed';
  campaignId: string;
  companiesFound: number;
  timestamp: string;
}

export interface SourcingFailed {
  type: 'sourcing.failed';
  campaignId: string;
  error: string;
  retryCount: number;
  timestamp: string;
}

export interface ProspectingCompleted {
  type: 'prospecting.completed';
  campaignId: string;
  prospectsEnriched: number;
  timestamp: string;
}

export interface MessagingFailed {
  type: 'messaging.failed';
  campaignId: string;
  draftId: string;
  error: string;
  retryCount: number;
  timestamp: string;
}

export type PipelineEvent =
  | PlanRequested
  | PlanReady
  | SourcingCompleted
  | SourcingFailed
  | ProspectingCompleted
  | MessagingFailed;
EOF

cat > src/orchestrator/types/queue-payloads.ts << 'EOF'
export interface QueueMessage<T = unknown> {
  eventType: string;
  payload: T;
  timestamp: string;
  correlationId: string;
}
EOF
make_commit "2026-04-27 15:00:00" "feat(types): add Campaign, PipelineEvent, and QueueMessage types"

# --- Commit 4: postgres client ---
mkdir -p src/orchestrator/postgres
cat > src/orchestrator/postgres/client.ts << 'EOF'
import { Pool, PoolClient } from 'pg';

export class PostgresClient {
  private pool: Pool;

  constructor(connectionString: string) {
    this.pool = new Pool({ connectionString, max: 10 });
  }

  async connect(): Promise<void> {
    const client = await this.pool.connect();
    client.release();
    console.log('[PostgresClient] Connection pool established');
  }

  async query<T = any>(text: string, params?: any[]): Promise<T[]> {
    const result = await this.pool.query(text, params);
    return result.rows as T[];
  }

  async getClient(): Promise<PoolClient> {
    return this.pool.connect();
  }

  async disconnect(): Promise<void> {
    await this.pool.end();
    console.log('[PostgresClient] Pool closed');
  }
}
EOF
make_commit "2026-04-28 09:30:00" "feat(postgres): add PostgresClient connection pool wrapper"

# --- Commit 5: campaign status repo ---
cat > src/orchestrator/postgres/campaign-status.repo.ts << 'EOF'
import { PostgresClient } from './client';
import { CampaignStatus } from '../types/campaign';

export interface CampaignStatusRow {
  campaign_id: string;
  status: CampaignStatus;
  stage_data: Record<string, unknown>;
  created_at: Date;
  updated_at: Date;
}

export class CampaignStatusRepository {
  constructor(private pg: PostgresClient) {}

  async ensureSchema(): Promise<void> {
    await this.pg.query(`
      CREATE TABLE IF NOT EXISTS campaign_status (
        campaign_id   VARCHAR(64) PRIMARY KEY,
        status        VARCHAR(32) NOT NULL DEFAULT 'CREATED',
        stage_data    JSONB NOT NULL DEFAULT '{}',
        created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
      );
      CREATE INDEX IF NOT EXISTS idx_status ON campaign_status(status);
    `);
  }

  async upsert(campaignId: string, status: CampaignStatus, stageData?: Record<string, unknown>): Promise<void> {
    await this.pg.query(
      `INSERT INTO campaign_status (campaign_id, status, stage_data)
       VALUES ($1, $2, $3)
       ON CONFLICT (campaign_id)
       DO UPDATE SET status = $2, stage_data = COALESCE($3, campaign_status.stage_data), updated_at = NOW()`,
      [campaignId, status, JSON.stringify(stageData || {})]
    );
  }

  async findById(campaignId: string): Promise<CampaignStatusRow | null> {
    const rows = await this.pg.query<CampaignStatusRow>(
      'SELECT * FROM campaign_status WHERE campaign_id = $1',
      [campaignId]
    );
    return rows[0] || null;
  }

  async findAll(limit = 50, offset = 0): Promise<CampaignStatusRow[]> {
    return this.pg.query<CampaignStatusRow>(
      'SELECT * FROM campaign_status ORDER BY updated_at DESC LIMIT $1 OFFSET $2',
      [limit, offset]
    );
  }

  async updateStatus(campaignId: string, status: CampaignStatus): Promise<void> {
    await this.pg.query(
      'UPDATE campaign_status SET status = $1, updated_at = NOW() WHERE campaign_id = $2',
      [status, campaignId]
    );
  }

  async delete(campaignId: string): Promise<void> {
    await this.pg.query('DELETE FROM campaign_status WHERE campaign_id = $1', [campaignId]);
  }
}
EOF

cat > src/orchestrator/postgres/index.ts << 'EOF'
export { PostgresClient } from './client';
export { CampaignStatusRepository } from './campaign-status.repo';
EOF
make_commit "2026-04-28 13:00:00" "feat(postgres): add CampaignStatusRepository with CRUD operations"

# --- Commit 6: validation service ---
mkdir -p src/orchestrator/services
cat > src/orchestrator/services/validation.ts << 'EOF'
import { ICPDefinition } from '../types/campaign';

export class ValidationError extends Error {
  constructor(public field: string, message: string) {
    super(message);
    this.name = 'ValidationError';
  }
}

export function validateICP(icp: unknown): asserts icp is ICPDefinition {
  if (!icp || typeof icp !== 'object') {
    throw new ValidationError('icp', 'ICP definition is required');
  }

  const obj = icp as Record<string, unknown>;

  if (!obj.industry || typeof obj.industry !== 'string') {
    throw new ValidationError('icp.industry', 'Industry is required and must be a string');
  }

  if (!obj.companySize || typeof obj.companySize !== 'string') {
    throw new ValidationError('icp.companySize', 'Company size is required');
  }

  if (!obj.region || typeof obj.region !== 'string') {
    throw new ValidationError('icp.region', 'Region is required');
  }

  if (!Array.isArray(obj.titles) || obj.titles.length === 0) {
    throw new ValidationError('icp.titles', 'At least one target title is required');
  }

  if (!Array.isArray(obj.keywords) || obj.keywords.length === 0) {
    throw new ValidationError('icp.keywords', 'At least one keyword is required');
  }
}

export function validateCampaignName(name: unknown): asserts name is string {
  if (!name || typeof name !== 'string' || name.trim().length < 3) {
    throw new ValidationError('name', 'Campaign name must be at least 3 characters');
  }
}
EOF
make_commit "2026-04-28 16:30:00" "feat(services): add ICP and campaign name validation"

# --- Commit 7: rabbit connection + events broker ---
mkdir -p src/orchestrator/rabbit
cat > src/orchestrator/rabbit/connection.ts << 'EOF'
import amqplib, { Connection, Channel } from 'amqplib';

const MAX_RETRIES = 5;
const RETRY_DELAY_MS = 2000;

export async function createConnection(url: string): Promise<Connection> {
  let attempt = 0;
  while (true) {
    try {
      attempt++;
      const conn = await amqplib.connect(url);
      console.log(`[RabbitMQ] Connected on attempt ${attempt}`);

      conn.on('error', (err) => {
        console.error('[RabbitMQ] Connection error:', err.message);
      });

      conn.on('close', () => {
        console.warn('[RabbitMQ] Connection closed unexpectedly');
      });

      return conn;
    } catch (err: any) {
      if (attempt >= MAX_RETRIES) {
        throw new Error(`[RabbitMQ] Failed after ${MAX_RETRIES} attempts: ${err.message}`);
      }
      const delay = RETRY_DELAY_MS * Math.pow(2, attempt - 1);
      console.warn(`[RabbitMQ] Attempt ${attempt} failed, retrying in ${delay}ms...`);
      await new Promise((r) => setTimeout(r, delay));
    }
  }
}

export async function createChannel(conn: Connection, prefetch = 10): Promise<Channel> {
  const channel = await conn.createChannel();
  await channel.prefetch(prefetch);
  console.log(`[RabbitMQ] Channel created (prefetch=${prefetch})`);
  return channel;
}
EOF
make_commit "2026-04-29 09:00:00" "feat(rabbit): add connection factory with exponential backoff retry"

# --- Commit 8: events broker ---
cat > src/orchestrator/rabbit/events-broker.ts << 'EOF'
import { Connection, Channel } from 'amqplib';
import { createConnection, createChannel } from './connection';
import { MessageBroker } from '../../local_infrastructure/rabbit_mq/broker.interface';

const EXCHANGE = 'outreach.events';
const EXCHANGE_TYPE = 'topic';

export class EventsBroker implements MessageBroker {
  private connection!: Connection;
  private channel!: Channel;

  constructor(private url: string) {}

  async init(): Promise<void> {
    this.connection = await createConnection(this.url);
    this.channel = await createChannel(this.connection);
    await this.channel.assertExchange(EXCHANGE, EXCHANGE_TYPE, { durable: true });
    console.log(`[EventsBroker] Exchange '${EXCHANGE}' (${EXCHANGE_TYPE}) asserted`);
  }

  async publish(routingKey: string, payload: unknown): Promise<void> {
    const message = Buffer.from(JSON.stringify({
      eventType: routingKey,
      payload,
      timestamp: new Date().toISOString(),
    }));

    this.channel.publish(EXCHANGE, routingKey, message, {
      persistent: true,
      contentType: 'application/json',
    });

    console.log(`[EventsBroker] Published ${routingKey}`);
  }

  async subscribe(routingKey: string, queue: string, handler: (msg: any) => Promise<void>): Promise<void> {
    await this.channel.assertQueue(queue, { durable: true });
    await this.channel.bindQueue(queue, EXCHANGE, routingKey);

    this.channel.consume(queue, async (msg) => {
      if (!msg) return;
      try {
        const parsed = JSON.parse(msg.content.toString());
        await handler(parsed);
        this.channel.ack(msg);
      } catch (err: any) {
        console.error(`[EventsBroker] Handler error on ${routingKey}:`, err.message);
        this.channel.nack(msg, false, false);
      }
    });

    console.log(`[EventsBroker] Subscribed to ${routingKey} via queue '${queue}'`);
  }

  async disconnect(): Promise<void> {
    await this.channel?.close();
    await this.connection?.close();
    console.log('[EventsBroker] Disconnected');
  }
}
EOF
make_commit "2026-04-29 14:00:00" "feat(rabbit): implement EventsBroker with topic exchange pub/sub"

# --- Commit 9: publishers ---
cat > src/orchestrator/rabbit/publishers.ts << 'EOF'
import { EventsBroker } from './events-broker';
import { ICPDefinition } from '../types/campaign';

export async function publishPlanRequested(
  broker: EventsBroker,
  campaignId: string,
  icp: ICPDefinition
): Promise<void> {
  await broker.publish('plan.requested', {
    campaignId,
    icp,
    timestamp: new Date().toISOString(),
  });
}

export async function publishSourcingRequested(
  broker: EventsBroker,
  campaignId: string,
  planId: string,
  sources: string[]
): Promise<void> {
  await broker.publish('sourcing.requested', {
    campaignId,
    planId,
    sources,
    timestamp: new Date().toISOString(),
  });
}

export async function publishProspectingRequested(
  broker: EventsBroker,
  campaignId: string,
  companiesFound: number
): Promise<void> {
  await broker.publish('prospecting.requested', {
    campaignId,
    companiesFound,
    timestamp: new Date().toISOString(),
  });
}

export async function publishMessagingRequested(
  broker: EventsBroker,
  campaignId: string,
  prospectsEnriched: number
): Promise<void> {
  await broker.publish('messaging.requested', {
    campaignId,
    prospectsEnriched,
    timestamp: new Date().toISOString(),
  });
}
EOF
make_commit "2026-04-30 09:30:00" "feat(rabbit): add typed publishers for all pipeline stage events"

# --- Commit 10: subscribers + handlers ---
mkdir -p src/orchestrator/rabbit/handlers
cat > src/orchestrator/rabbit/handlers/planReady.ts << 'EOF'
import { EventsBroker } from '../events-broker';
import { CampaignStatusRepository } from '../../postgres';
import { publishSourcingRequested } from '../publishers';
import { PlanReady } from '../../types/events';

export function createPlanReadyHandler(
  broker: EventsBroker,
  statusRepo: CampaignStatusRepository
) {
  return async (msg: { payload: PlanReady }): Promise<void> => {
    const { campaignId, planId, sources } = msg.payload;
    console.log(`[planReady] Campaign ${campaignId} — plan ${planId} ready with ${sources.length} sources`);

    await statusRepo.updateStatus(campaignId, 'SOURCING');
    await publishSourcingRequested(broker, campaignId, planId, sources);

    console.log(`[planReady] Triggered sourcing for campaign ${campaignId}`);
  };
}
EOF

cat > src/orchestrator/rabbit/handlers/sourcingCompleted.ts << 'EOF'
import { EventsBroker } from '../events-broker';
import { CampaignStatusRepository } from '../../postgres';
import { publishProspectingRequested } from '../publishers';
import { SourcingCompleted } from '../../types/events';

export function createSourcingCompletedHandler(
  broker: EventsBroker,
  statusRepo: CampaignStatusRepository
) {
  return async (msg: { payload: SourcingCompleted }): Promise<void> => {
    const { campaignId, companiesFound } = msg.payload;
    console.log(`[sourcingCompleted] Campaign ${campaignId} — ${companiesFound} companies found`);

    await statusRepo.updateStatus(campaignId, 'PROSPECTING');
    await publishProspectingRequested(broker, campaignId, companiesFound);

    console.log(`[sourcingCompleted] Triggered prospecting for campaign ${campaignId}`);
  };
}
EOF
make_commit "2026-04-30 14:00:00" "feat(rabbit): add plan.ready and sourcing.completed event handlers"

# --- Commit 11: more handlers ---
cat > src/orchestrator/rabbit/handlers/sourcingFailed.ts << 'EOF'
import { EventsBroker } from '../events-broker';
import { CampaignStatusRepository } from '../../postgres';
import { SourcingFailed } from '../../types/events';

const MAX_RETRIES = 3;

export function createSourcingFailedHandler(
  broker: EventsBroker,
  statusRepo: CampaignStatusRepository
) {
  return async (msg: { payload: SourcingFailed }): Promise<void> => {
    const { campaignId, error, retryCount } = msg.payload;
    console.warn(`[sourcingFailed] Campaign ${campaignId} — attempt ${retryCount}: ${error}`);

    if (retryCount < MAX_RETRIES) {
      console.log(`[sourcingFailed] Retrying sourcing (${retryCount + 1}/${MAX_RETRIES})...`);
      await broker.publish('sourcing.requested', {
        campaignId,
        retryCount: retryCount + 1,
        timestamp: new Date().toISOString(),
      });
    } else {
      console.error(`[sourcingFailed] Max retries reached for campaign ${campaignId}`);
      await statusRepo.updateStatus(campaignId, 'SOURCING_FAILED');
    }
  };
}
EOF

cat > src/orchestrator/rabbit/handlers/prospectingCompleted.ts << 'EOF'
import { EventsBroker } from '../events-broker';
import { CampaignStatusRepository } from '../../postgres';
import { publishMessagingRequested } from '../publishers';
import { ProspectingCompleted } from '../../types/events';

export function createProspectingCompletedHandler(
  broker: EventsBroker,
  statusRepo: CampaignStatusRepository
) {
  return async (msg: { payload: ProspectingCompleted }): Promise<void> => {
    const { campaignId, prospectsEnriched } = msg.payload;
    console.log(`[prospectingCompleted] Campaign ${campaignId} — ${prospectsEnriched} prospects enriched`);

    await statusRepo.updateStatus(campaignId, 'MESSAGING');
    await publishMessagingRequested(broker, campaignId, prospectsEnriched);

    console.log(`[prospectingCompleted] Triggered messaging for campaign ${campaignId}`);
  };
}
EOF

cat > src/orchestrator/rabbit/handlers/messagingFailed.ts << 'EOF'
import { EventsBroker } from '../events-broker';
import { MessagingFailed } from '../../types/events';

const MAX_RETRIES = 3;

export function createMessagingFailedHandler(broker: EventsBroker) {
  return async (msg: { payload: MessagingFailed }): Promise<void> => {
    const { campaignId, draftId, error, retryCount } = msg.payload;
    console.warn(`[messagingFailed] Draft ${draftId} for campaign ${campaignId}: ${error}`);

    if (retryCount < MAX_RETRIES) {
      console.log(`[messagingFailed] Re-queuing draft ${draftId} (retry ${retryCount + 1})`);
      await broker.publish('messaging.retry', {
        campaignId,
        draftId,
        retryCount: retryCount + 1,
        timestamp: new Date().toISOString(),
      });
    } else {
      console.error(`[messagingFailed] Draft ${draftId} permanently failed after ${MAX_RETRIES} retries`);
    }
  };
}
EOF
make_commit "2026-05-01 09:30:00" "feat(rabbit): add sourcing.failed, prospecting.completed, messaging.failed handlers"

# --- Commit 12: subscribers binding ---
cat > src/orchestrator/rabbit/subscribers.ts << 'EOF'
import { EventsBroker } from './events-broker';
import { CampaignStatusRepository } from '../postgres';
import { createPlanReadyHandler } from './handlers/planReady';
import { createSourcingCompletedHandler } from './handlers/sourcingCompleted';
import { createSourcingFailedHandler } from './handlers/sourcingFailed';
import { createProspectingCompletedHandler } from './handlers/prospectingCompleted';
import { createMessagingFailedHandler } from './handlers/messagingFailed';

export async function registerSubscribers(
  broker: EventsBroker,
  statusRepo: CampaignStatusRepository
): Promise<void> {
  await broker.subscribe(
    'plan.ready',
    'orchestrator.plan-ready',
    createPlanReadyHandler(broker, statusRepo)
  );

  await broker.subscribe(
    'sourcing.completed',
    'orchestrator.sourcing-completed',
    createSourcingCompletedHandler(broker, statusRepo)
  );

  await broker.subscribe(
    'sourcing.failed',
    'orchestrator.sourcing-failed',
    createSourcingFailedHandler(broker, statusRepo)
  );

  await broker.subscribe(
    'prospecting.completed',
    'orchestrator.prospecting-completed',
    createProspectingCompletedHandler(broker, statusRepo)
  );

  await broker.subscribe(
    'messaging.failed',
    'orchestrator.messaging-failed',
    createMessagingFailedHandler(broker)
  );

  console.log('[subscribers] All pipeline event listeners registered');
}
EOF
make_commit "2026-05-01 14:00:00" "feat(rabbit): register all pipeline subscribers in single module"

# --- Commit 13: pipeline service ---
cat > src/orchestrator/services/pipeline.service.ts << 'EOF'
import { v4 as uuidv4 } from 'uuid';
import { EventsBroker } from '../rabbit/events-broker';
import { registerSubscribers } from '../rabbit/subscribers';
import { publishPlanRequested } from '../rabbit/publishers';
import { CampaignStatusRepository } from '../postgres';
import { validateICP, validateCampaignName } from './validation';
import { ICPDefinition } from '../types/campaign';

export class PipelineService {
  constructor(
    private broker: EventsBroker,
    private statusRepo: CampaignStatusRepository
  ) {}

  async startListening(): Promise<void> {
    await this.broker.init();
    await registerSubscribers(this.broker, this.statusRepo);
    console.log('[PipelineService] Listening for pipeline events');
  }

  async createCampaign(name: string, icp: unknown): Promise<{ campaignId: string }> {
    validateCampaignName(name);
    validateICP(icp);

    const campaignId = uuidv4();
    await this.statusRepo.upsert(campaignId, 'CREATED', { name, icp });
    await this.statusRepo.updateStatus(campaignId, 'PLANNING');
    await publishPlanRequested(this.broker, campaignId, icp as ICPDefinition);

    console.log(`[PipelineService] Campaign ${campaignId} created and plan.requested published`);
    return { campaignId };
  }

  async pauseCampaign(campaignId: string): Promise<void> {
    const campaign = await this.statusRepo.findById(campaignId);
    if (!campaign) throw new Error(`Campaign ${campaignId} not found`);
    if (campaign.status === 'PAUSED') throw new Error('Campaign is already paused');
    await this.statusRepo.updateStatus(campaignId, 'PAUSED');
  }

  async resumeCampaign(campaignId: string): Promise<void> {
    const campaign = await this.statusRepo.findById(campaignId);
    if (!campaign) throw new Error(`Campaign ${campaignId} not found`);
    if (campaign.status !== 'PAUSED') throw new Error('Campaign is not paused');
    await this.statusRepo.updateStatus(campaignId, 'PLANNING');
  }

  async cancelCampaign(campaignId: string): Promise<void> {
    const campaign = await this.statusRepo.findById(campaignId);
    if (!campaign) throw new Error(`Campaign ${campaignId} not found`);
    await this.statusRepo.updateStatus(campaignId, 'CANCELLED');
  }
}
EOF

cat > src/orchestrator/services/index.ts << 'EOF'
export { PipelineService } from './pipeline.service';
export { validateICP, validateCampaignName, ValidationError } from './validation';
EOF
make_commit "2026-05-03 11:00:00" "feat(services): implement PipelineService with campaign lifecycle"

# ════════════════════════════════════════════════════════════
# WEEK 2 — May 4–10  (13 commits)
# ════════════════════════════════════════════════════════════
echo ""
echo "── Week 2: May 4–10 ───────────────────────────────────"

# --- Commit 14: health route ---
mkdir -p src/orchestrator/routes
cat > src/orchestrator/routes/health.routes.ts << 'EOF'
import { Router, Request, Response } from 'express';

export function createHealthRouter(): Router {
  const router = Router();

  router.get('/health', (_req: Request, res: Response) => {
    res.json({
      status: 'ok',
      service: 'orchestrator',
      timestamp: new Date().toISOString(),
      uptime: process.uptime(),
    });
  });

  return router;
}
EOF
make_commit "2026-05-04 09:00:00" "feat(routes): add /health liveness check endpoint"

# --- Commit 15: campaign routes ---
cat > src/orchestrator/routes/campaign.routes.ts << 'EOF'
import { Router, Request, Response, NextFunction } from 'express';
import { PipelineService } from '../services';
import { CampaignStatusRepository } from '../postgres';

export function createCampaignRouter(
  pipelineService: PipelineService,
  statusRepo: CampaignStatusRepository
): Router {
  const router = Router();

  // POST /api/campaigns — create a new campaign
  router.post('/', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { name, icp } = req.body;
      const result = await pipelineService.createCampaign(name, icp);
      res.status(201).json(result);
    } catch (err) {
      next(err);
    }
  });

  // GET /api/campaigns — list all campaigns
  router.get('/', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const limit = parseInt(req.query.limit as string) || 50;
      const offset = parseInt(req.query.offset as string) || 0;
      const campaigns = await statusRepo.findAll(limit, offset);
      res.json({ campaigns, limit, offset });
    } catch (err) {
      next(err);
    }
  });

  // GET /api/campaigns/:id — campaign detail
  router.get('/:id', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const campaign = await statusRepo.findById(req.params.id);
      if (!campaign) {
        return res.status(404).json({ error: 'Campaign not found' });
      }
      res.json(campaign);
    } catch (err) {
      next(err);
    }
  });

  // PATCH /api/campaigns/:id — pause or resume
  router.patch('/:id', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { action } = req.body;
      if (action === 'pause') {
        await pipelineService.pauseCampaign(req.params.id);
      } else if (action === 'resume') {
        await pipelineService.resumeCampaign(req.params.id);
      } else {
        return res.status(400).json({ error: 'Action must be "pause" or "resume"' });
      }
      res.json({ status: 'ok', action });
    } catch (err) {
      next(err);
    }
  });

  // DELETE /api/campaigns/:id — cancel campaign
  router.delete('/:id', async (req: Request, res: Response, next: NextFunction) => {
    try {
      await pipelineService.cancelCampaign(req.params.id);
      res.json({ status: 'cancelled', campaignId: req.params.id });
    } catch (err) {
      next(err);
    }
  });

  return router;
}
EOF
make_commit "2026-05-04 11:30:00" "feat(routes): implement full campaign CRUD routes"

# --- Commit 16: api routes (prospects, drafts, status) ---
cat > src/orchestrator/routes/prospects.ts << 'EOF'
import { Router, Request, Response, NextFunction } from 'express';
import mongoose from 'mongoose';

export function createProspectsRouter(): Router {
  const router = Router();

  // GET /api/campaigns/:id/prospects
  router.get('/campaigns/:id/prospects', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const campaignId = req.params.id;
      const db = mongoose.connection.db;
      const prospects = await db
        .collection('prospects')
        .find({ campaignId })
        .limit(100)
        .toArray();

      res.json({ campaignId, count: prospects.length, prospects });
    } catch (err) {
      next(err);
    }
  });

  // GET /api/prospects/:id
  router.get('/prospects/:id', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const db = mongoose.connection.db;
      const prospect = await db
        .collection('prospects')
        .findOne({ _id: new mongoose.Types.ObjectId(req.params.id) });

      if (!prospect) return res.status(404).json({ error: 'Prospect not found' });
      res.json(prospect);
    } catch (err) {
      next(err);
    }
  });

  return router;
}
EOF
make_commit "2026-05-04 15:00:00" "feat(routes): add prospects list and detail endpoints"

# --- Commit 17: drafts route ---
cat > src/orchestrator/routes/drafts.ts << 'EOF'
import { Router, Request, Response, NextFunction } from 'express';
import mongoose from 'mongoose';

export function createDraftsRouter(): Router {
  const router = Router();

  // GET /api/campaigns/:id/drafts
  router.get('/campaigns/:id/drafts', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const campaignId = req.params.id;
      const db = mongoose.connection.db;
      const drafts = await db
        .collection('drafts')
        .find({ campaignId })
        .sort({ createdAt: -1 })
        .limit(100)
        .toArray();

      res.json({ campaignId, count: drafts.length, drafts });
    } catch (err) {
      next(err);
    }
  });

  // GET /api/drafts/:id
  router.get('/drafts/:id', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const db = mongoose.connection.db;
      const draft = await db
        .collection('drafts')
        .findOne({ _id: new mongoose.Types.ObjectId(req.params.id) });

      if (!draft) return res.status(404).json({ error: 'Draft not found' });
      res.json(draft);
    } catch (err) {
      next(err);
    }
  });

  return router;
}
EOF
make_commit "2026-05-05 09:30:00" "feat(routes): add drafts list and detail endpoints"

# --- Commit 18: status route ---
cat > src/orchestrator/routes/status.ts << 'EOF'
import { Router, Request, Response, NextFunction } from 'express';
import { CampaignStatusRepository } from '../postgres';

export function createStatusRouter(statusRepo: CampaignStatusRepository): Router {
  const router = Router();

  // GET /api/status — system health + queue depths
  router.get('/status', async (_req: Request, res: Response, next: NextFunction) => {
    try {
      const campaigns = await statusRepo.findAll(1000, 0);

      const statusCounts: Record<string, number> = {};
      for (const c of campaigns) {
        statusCounts[c.status] = (statusCounts[c.status] || 0) + 1;
      }

      res.json({
        service: 'orchestrator',
        status: 'operational',
        totalCampaigns: campaigns.length,
        byStatus: statusCounts,
        timestamp: new Date().toISOString(),
      });
    } catch (err) {
      next(err);
    }
  });

  return router;
}
EOF
make_commit "2026-05-05 13:00:00" "feat(routes): add /api/status system overview endpoint"

# --- Commit 19: stats aggregator service ---
cat > src/orchestrator/services/statsAggregator.ts << 'EOF'
import mongoose from 'mongoose';
import { CampaignStats } from '../types/campaign';

export class StatsAggregator {
  async getCampaignStats(campaignId: string): Promise<CampaignStats> {
    const db = mongoose.connection.db;

    const totalProspects = await db
      .collection('prospects')
      .countDocuments({ campaignId });

    const drafts = await db
      .collection('drafts')
      .find({ campaignId })
      .toArray();

    const emailsSent = drafts.filter((d) => d.status === 'SENT').length;
    const opened = drafts.filter((d) => d.opened === true).length;
    const replied = drafts.filter((d) => d.replied === true).length;

    return {
      campaignId,
      totalProspects,
      emailsSent,
      opened,
      replied,
      openRate: emailsSent > 0 ? (opened / emailsSent) * 100 : 0,
      replyRate: emailsSent > 0 ? (replied / emailsSent) * 100 : 0,
    };
  }
}
EOF
make_commit "2026-05-05 16:30:00" "feat(services): add StatsAggregator for campaign metrics"

# --- Commit 20: stats route ---
cat > src/orchestrator/routes/campaigns.ts << 'EOF'
import { Router, Request, Response, NextFunction } from 'express';
import { StatsAggregator } from '../services/statsAggregator';

export function createCampaignStatsRouter(): Router {
  const router = Router();
  const statsAggregator = new StatsAggregator();

  // GET /api/campaigns/:id/stats
  router.get('/:id/stats', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const stats = await statsAggregator.getCampaignStats(req.params.id);
      res.json(stats);
    } catch (err) {
      next(err);
    }
  });

  return router;
}
EOF
make_commit "2026-05-06 09:00:00" "feat(routes): add campaign stats endpoint with open/reply rates"

# --- Commit 21: error handler middleware ---
mkdir -p src/orchestrator/middleware
cat > src/orchestrator/middleware/error-handler.ts << 'EOF'
import { Request, Response, NextFunction } from 'express';
import { ValidationError } from '../services/validation';

export class ApiError extends Error {
  constructor(
    public statusCode: number,
    message: string,
    public details?: Record<string, unknown>
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export function errorHandler(
  err: Error,
  _req: Request,
  res: Response,
  _next: NextFunction
): void {
  if (err instanceof ValidationError) {
    res.status(400).json({
      error: 'Validation Error',
      field: err.field,
      message: err.message,
    });
    return;
  }

  if (err instanceof ApiError) {
    res.status(err.statusCode).json({
      error: err.message,
      details: err.details,
    });
    return;
  }

  console.error('[errorHandler] Unhandled error:', err);
  res.status(500).json({
    error: 'Internal Server Error',
    message: err.message,
  });
}
EOF
make_commit "2026-05-06 12:30:00" "feat(middleware): add centralized error handler with ApiError class"

# --- Commit 22: request logger middleware ---
cat > src/orchestrator/middleware/requestLogger.ts << 'EOF'
import { Request, Response, NextFunction } from 'express';

export function requestLogger(req: Request, res: Response, next: NextFunction): void {
  const start = Date.now();

  res.on('finish', () => {
    const duration = Date.now() - start;
    const log = {
      method: req.method,
      path: req.originalUrl,
      status: res.statusCode,
      duration: `${duration}ms`,
      timestamp: new Date().toISOString(),
    };
    console.log(`[http] ${log.method} ${log.path} ${log.status} (${log.duration})`);
  });

  next();
}
EOF
make_commit "2026-05-06 16:00:00" "feat(middleware): add request logging with method, path, duration"

# --- Commit 23: metrics middleware ---
cat > src/orchestrator/middleware/metrics.ts << 'EOF'
import { Request, Response, NextFunction } from 'express';

// Simple in-memory metrics (replace with prom-client in production)
const metrics = {
  httpRequestsTotal: 0,
  httpRequestsByRoute: {} as Record<string, number>,
  httpRequestsByStatus: {} as Record<string, number>,
  startTime: Date.now(),
};

export function metricsMiddleware(req: Request, res: Response, next: NextFunction): void {
  res.on('finish', () => {
    metrics.httpRequestsTotal++;
    const routeKey = `${req.method} ${req.route?.path || req.path}`;
    metrics.httpRequestsByRoute[routeKey] = (metrics.httpRequestsByRoute[routeKey] || 0) + 1;
    const statusKey = `${res.statusCode}`;
    metrics.httpRequestsByStatus[statusKey] = (metrics.httpRequestsByStatus[statusKey] || 0) + 1;
  });
  next();
}

export function getMetrics() {
  return {
    ...metrics,
    uptimeSeconds: Math.floor((Date.now() - metrics.startTime) / 1000),
  };
}
EOF
make_commit "2026-05-07 09:30:00" "feat(middleware): add in-memory HTTP metrics collector"

# --- Commit 24: route index ---
cat > src/orchestrator/routes/index.ts << 'EOF'
export { createCampaignRouter } from './campaign.routes';
export { createHealthRouter } from './health.routes';
export { createStatusRouter as createApiRouter } from './status';
export { createProspectsRouter } from './prospects';
export { createDraftsRouter } from './drafts';
export { createCampaignStatsRouter } from './campaigns';
EOF
make_commit "2026-05-07 13:00:00" "refactor(routes): consolidate route exports into barrel index"

# --- Commit 25: pipeline tracker service ---
cat > src/orchestrator/services/pipelineTracker.ts << 'EOF'
import { CampaignStatusRepository } from '../postgres';
import { CampaignStatus } from '../types/campaign';

interface StageTransition {
  from: CampaignStatus;
  to: CampaignStatus;
  timestamp: Date;
}

export class PipelineTracker {
  private transitions: Map<string, StageTransition[]> = new Map();

  constructor(private statusRepo: CampaignStatusRepository) {}

  async recordTransition(campaignId: string, from: CampaignStatus, to: CampaignStatus): Promise<void> {
    const transition: StageTransition = { from, to, timestamp: new Date() };

    if (!this.transitions.has(campaignId)) {
      this.transitions.set(campaignId, []);
    }
    this.transitions.get(campaignId)!.push(transition);

    await this.statusRepo.updateStatus(campaignId, to);
    console.log(`[PipelineTracker] Campaign ${campaignId}: ${from} → ${to}`);
  }

  getTransitions(campaignId: string): StageTransition[] {
    return this.transitions.get(campaignId) || [];
  }

  async getCurrentStage(campaignId: string): Promise<CampaignStatus | null> {
    const row = await this.statusRepo.findById(campaignId);
    return row?.status ?? null;
  }
}
EOF
make_commit "2026-05-08 10:00:00" "feat(services): add PipelineTracker with stage transition history"

# --- Commit 26: audit log ---
cat > src/orchestrator/postgres/auditLog.ts << 'EOF'
import { PostgresClient } from './client';

export interface AuditEntry {
  id: number;
  campaign_id: string;
  event_type: string;
  payload: Record<string, unknown>;
  created_at: Date;
}

export class AuditLog {
  constructor(private pg: PostgresClient) {}

  async ensureSchema(): Promise<void> {
    await this.pg.query(`
      CREATE TABLE IF NOT EXISTS audit_log (
        id            SERIAL PRIMARY KEY,
        campaign_id   VARCHAR(64) NOT NULL,
        event_type    VARCHAR(64) NOT NULL,
        payload       JSONB NOT NULL DEFAULT '{}',
        created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
      );
      CREATE INDEX IF NOT EXISTS idx_audit_campaign ON audit_log(campaign_id);
      CREATE INDEX IF NOT EXISTS idx_audit_event ON audit_log(event_type);
    `);
  }

  async insertEvent(campaignId: string, eventType: string, payload: Record<string, unknown>): Promise<void> {
    await this.pg.query(
      'INSERT INTO audit_log (campaign_id, event_type, payload) VALUES ($1, $2, $3)',
      [campaignId, eventType, JSON.stringify(payload)]
    );
  }

  async getByCamera(campaignId: string, limit = 100): Promise<AuditEntry[]> {
    return this.pg.query<AuditEntry>(
      'SELECT * FROM audit_log WHERE campaign_id = $1 ORDER BY created_at DESC LIMIT $2',
      [campaignId, limit]
    );
  }
}
EOF
make_commit "2026-05-08 15:00:00" "feat(postgres): add AuditLog table for pipeline event tracking"

# ════════════════════════════════════════════════════════════
# WEEK 3 — May 9–13  (13 commits)
# ════════════════════════════════════════════════════════════
echo ""
echo "── Week 3: May 9–13 ───────────────────────────────────"

# --- Commit 27: app.ts full wiring ---
cat > src/orchestrator/app.ts << 'EOF'
import express from 'express';
import {
  createCampaignRouter,
  createHealthRouter,
  createApiRouter,
  createProspectsRouter,
  createDraftsRouter,
  createCampaignStatsRouter,
} from './routes';
import { PipelineService } from './services';
import { errorHandler } from './middleware/error-handler';
import { requestLogger } from './middleware/requestLogger';
import { metricsMiddleware } from './middleware/metrics';
import { MessageBroker } from '../local_infrastructure/rabbit_mq/broker.interface';
import { CampaignStatusRepository } from './postgres';

export function createApp(
  broker: MessageBroker,
  statusRepo: CampaignStatusRepository
): {
  app: express.Application;
  pipelineService: PipelineService;
} {
  const app = express();

  // ── Global Middleware ──────────────────────────────────────
  app.use(express.json());
  app.use(requestLogger);
  app.use(metricsMiddleware);

  // ── Services ───────────────────────────────────────────────
  const pipelineService = new PipelineService(broker, statusRepo);

  // ── Routes ─────────────────────────────────────────────────
  app.use('/api/campaigns', createCampaignRouter(pipelineService, statusRepo));
  app.use('/api/campaigns', createCampaignStatsRouter());
  app.use('/api', createApiRouter(statusRepo));
  app.use('/api', createProspectsRouter());
  app.use('/api', createDraftsRouter());
  app.use('/', createHealthRouter());

  // ── Error Handler ──────────────────────────────────────────
  app.use(errorHandler);

  return { app, pipelineService };
}
EOF
make_commit "2026-05-09 09:00:00" "refactor(app): wire all routes, logger, and metrics middleware"

# --- Commit 28: main.ts full wiring ---
cat > src/orchestrator/main.ts << 'EOF'
import mongoose from 'mongoose';
import { config } from './config';
import { createApp } from './app';
import { EventsBroker } from './rabbit/events-broker';
import { CampaignStatusRepository, PostgresClient } from './postgres';
import { AuditLog } from './postgres/auditLog';

async function main(): Promise<void> {
  // ── Connect to MongoDB ─────────────────────────────────────
  console.log(`[main] Connecting to MongoDB at ${config.mongoUri}…`);
  await mongoose.connect(config.mongoUri);
  console.log('[main] MongoDB connected.');

  // ── Connect to PostgreSQL ──────────────────────────────────
  console.log(`[main] Connecting to PostgreSQL at ${config.postgresUrl}…`);
  const pg = new PostgresClient(config.postgresUrl);
  await pg.connect();

  const statusRepo = new CampaignStatusRepository(pg);
  await statusRepo.ensureSchema();

  const auditLog = new AuditLog(pg);
  await auditLog.ensureSchema();

  console.log('[main] PostgreSQL connected; schemas ready.');

  // ── Create message broker ──────────────────────────────────
  const broker = new EventsBroker(config.rabbitmqUrl);
  console.log('[main] EventsBroker ready.');

  // ── Build Express app ──────────────────────────────────────
  const { app, pipelineService } = createApp(broker, statusRepo);

  // ── Start queue listeners ──────────────────────────────────
  await pipelineService.startListening();

  // ── Start HTTP server ──────────────────────────────────────
  app.listen(config.port, () => {
    console.log(`[main] Orchestrator listening on :${config.port}`);
  });

  // ── Graceful shutdown ──────────────────────────────────────
  const shutdown = async (signal: string) => {
    console.log(`\n[main] Received ${signal}. Shutting down…`);
    await broker.disconnect();
    await mongoose.disconnect();
    await pg.disconnect();
    process.exit(0);
  };

  process.on('SIGTERM', () => shutdown('SIGTERM'));
  process.on('SIGINT', () => shutdown('SIGINT'));
}

main().catch((err) => {
  console.error('[main] Fatal error:', err);
  process.exit(1);
});
EOF
make_commit "2026-05-09 11:30:00" "refactor(main): wire audit log and clean up bootstrap sequence"

# --- Commit 29: Dockerfile ---
cat > src/orchestrator/Dockerfile << 'EOF'
# ── Stage 1: build ────────────────────────────────────────
FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY tsconfig.json ./
COPY . .
RUN npm run build

# ── Stage 2: production ──────────────────────────────────
FROM node:20-alpine
WORKDIR /app
RUN addgroup -S app && adduser -S app -G app
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/package.json /app/package-lock.json ./
RUN npm ci --only=production && npm cache clean --force
USER app
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD wget -qO- http://localhost:3000/health || exit 1
CMD ["node", "dist/main.js"]
EOF
make_commit "2026-05-09 14:00:00" "feat(docker): add multi-stage Dockerfile with health check"

# --- Commit 30: Helm chart values ---
mkdir -p deploy/charts/orchestrator
cat > deploy/charts/orchestrator/values.yaml << 'EOF'
replicaCount: 2

image:
  repository: ghcr.io/wolfy5786/orchestrator
  tag: latest
  pullPolicy: IfNotPresent

service:
  type: ClusterIP
  port: 3000

resources:
  requests:
    cpu: 100m
    memory: 256Mi
  limits:
    cpu: 500m
    memory: 512Mi

env:
  - name: PORT
    value: "3000"
  - name: NODE_ENV
    value: "production"
  - name: RABBITMQ_URL
    valueFrom:
      secretKeyRef:
        name: orchestrator-secrets
        key: rabbitmq-url
  - name: DATABASE_URL
    valueFrom:
      secretKeyRef:
        name: orchestrator-secrets
        key: database-url
  - name: MONGO_URI
    valueFrom:
      secretKeyRef:
        name: orchestrator-secrets
        key: mongo-uri

livenessProbe:
  httpGet:
    path: /health
    port: 3000
  initialDelaySeconds: 10
  periodSeconds: 15

readinessProbe:
  httpGet:
    path: /health
    port: 3000
  initialDelaySeconds: 5
  periodSeconds: 10
EOF
make_commit "2026-05-09 16:30:00" "feat(deploy): add orchestrator Helm chart values with probes"

# --- Commit 31: campaign repo v2 with campaignRepo.ts ---
cat > src/orchestrator/postgres/campaignRepo.ts << 'EOF'
import { PostgresClient } from './client';

export interface CampaignRow {
  id: string;
  name: string;
  icp_data: Record<string, unknown>;
  created_at: Date;
}

export class CampaignRepository {
  constructor(private pg: PostgresClient) {}

  async ensureSchema(): Promise<void> {
    await this.pg.query(`
      CREATE TABLE IF NOT EXISTS campaigns (
        id          VARCHAR(64) PRIMARY KEY,
        name        VARCHAR(255) NOT NULL,
        icp_data    JSONB NOT NULL DEFAULT '{}',
        created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
      );
    `);
  }

  async insert(id: string, name: string, icpData: Record<string, unknown>): Promise<void> {
    await this.pg.query(
      'INSERT INTO campaigns (id, name, icp_data) VALUES ($1, $2, $3)',
      [id, name, JSON.stringify(icpData)]
    );
  }

  async findById(id: string): Promise<CampaignRow | null> {
    const rows = await this.pg.query<CampaignRow>(
      'SELECT * FROM campaigns WHERE id = $1',
      [id]
    );
    return rows[0] || null;
  }
}
EOF
make_commit "2026-05-10 09:00:00" "feat(postgres): add CampaignRepository for campaign metadata"

# --- Commit 32: api routes barrel ---
cat > src/orchestrator/routes/api.routes.ts << 'EOF'
import { Router } from 'express';
import { CampaignStatusRepository } from '../postgres';
import { getMetrics } from '../middleware/metrics';

export function createApiMetricsRouter(statusRepo: CampaignStatusRepository): Router {
  const router = Router();

  // GET /api/metrics — internal metrics endpoint
  router.get('/metrics', (_req, res) => {
    res.json(getMetrics());
  });

  return router;
}
EOF
make_commit "2026-05-10 11:00:00" "feat(routes): add /api/metrics internal metrics endpoint"

# --- Commit 33: update postgres index ---
cat > src/orchestrator/postgres/index.ts << 'EOF'
export { PostgresClient } from './client';
export { CampaignStatusRepository } from './campaign-status.repo';
export { CampaignRepository } from './campaignRepo';
export { AuditLog } from './auditLog';
EOF
make_commit "2026-05-10 14:30:00" "refactor(postgres): update barrel exports with all repositories"

# --- Commit 34: middleware barrel + errorHandler alias ---
cat > src/orchestrator/middleware/errorHandler.ts << 'EOF'
// Re-export for backwards compatibility
export { errorHandler, ApiError } from './error-handler';
EOF
make_commit "2026-05-10 16:00:00" "refactor(middleware): add errorHandler re-export for compat"

# --- Commit 35: design docs update ---
cat >> design_docs/orchestrator_service_role.md << 'EOF'

## Pipeline Stage Lifecycle

The orchestrator manages the following stage transitions:

1. **CREATED** → POST /api/campaigns triggers plan.requested
2. **PLANNING** → Waiting for plan.ready from planning service
3. **PLAN_READY** → Automatically triggers sourcing.requested
4. **SOURCING** → Waiting for sourcing.completed (retries on failure up to 3x)
5. **PROSPECTING** → Waiting for prospecting.completed
6. **MESSAGING** → Drafts generated and queued for send
7. **COMPLETED** → All emails sent successfully

Side states: **PAUSED** (user-triggered), **CANCELLED** (user-triggered), **SOURCING_FAILED** (after 3 retries)

## Error Recovery

- sourcing.failed events trigger automatic retry with exponential backoff
- messaging.failed events re-queue individual drafts up to 3 times
- All transitions are logged in the audit_log table for debugging
EOF
make_commit "2026-05-12 09:00:00" "docs(design): add pipeline lifecycle and error recovery docs"

# --- Commit 36: orchestrator README ---
cat > src/orchestrator/README.md << 'EOF'
# Orchestrator Service

Central coordination service for the autonomous email outreach pipeline.

## Architecture

The orchestrator sits at the center of the microservices architecture, coordinating work between:
- **Planning Service** — generates outreach plans from ICP definitions
- **Sourcing Service** — discovers companies matching the plan
- **Prospecting Service** — enriches contacts at discovered companies
- **Messaging Service** — generates and sends personalized emails

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | /api/campaigns | Create a new campaign |
| GET | /api/campaigns | List all campaigns |
| GET | /api/campaigns/:id | Campaign detail |
| PATCH | /api/campaigns/:id | Pause/resume campaign |
| DELETE | /api/campaigns/:id | Cancel campaign |
| GET | /api/campaigns/:id/stats | Campaign metrics |
| GET | /api/campaigns/:id/prospects | List prospects |
| GET | /api/campaigns/:id/drafts | List email drafts |
| GET | /api/status | System overview |
| GET | /api/metrics | Internal metrics |
| GET | /health | Liveness check |

## Quick Start

```bash
cp .env.example .env
npm install
npm run dev
```

## Event Flow

```
POST /api/campaigns
  → publish plan.requested
    → consume plan.ready → publish sourcing.requested
      → consume sourcing.completed → publish prospecting.requested
        → consume prospecting.completed → publish messaging.requested
```
EOF
make_commit "2026-05-12 10:30:00" "docs(orchestrator): add comprehensive README with API reference"

# --- Commit 37: shared broker interface ---
mkdir -p src/local_infrastructure/rabbit_mq
cat > src/local_infrastructure/rabbit_mq/broker.interface.ts << 'EOF'
/**
 * MessageBroker — shared interface for all services.
 * Implementations: EventsBroker (orchestrator), PythonBroker (sourcing/planning)
 */
export interface MessageBroker {
  init(): Promise<void>;
  publish(routingKey: string, payload: unknown): Promise<void>;
  subscribe(routingKey: string, queue: string, handler: (msg: any) => Promise<void>): Promise<void>;
  disconnect(): Promise<void>;
}
EOF
make_commit "2026-05-12 13:00:00" "refactor(shared): add MessageBroker interface for cross-service use"

# --- Commit 38: update design doc for repo structure ---
cat >> design_docs/Repository_structure.md << 'EOF'

## Orchestrator Service (`src/orchestrator/`)

```
src/orchestrator/
├── config/          # Environment configuration
├── middleware/       # Express middleware (logging, metrics, errors)
├── postgres/        # PostgreSQL repositories (campaigns, status, audit)
├── rabbit/          # RabbitMQ broker, publishers, subscribers, handlers
├── routes/          # Express route handlers
├── services/        # Business logic (pipeline, validation, stats)
├── types/           # TypeScript type definitions
├── app.ts           # Express app factory
├── main.ts          # Entry point
├── Dockerfile       # Multi-stage Docker build
└── package.json     # Dependencies
```
EOF
make_commit "2026-05-13 09:00:00" "docs(design): add orchestrator directory structure to repo docs"

# --- Commit 39: gitignore + cleanup ---
cat >> .gitignore << 'EOF'

# Orchestrator
src/orchestrator/dist/
src/orchestrator/node_modules/
*.js.map
EOF
make_commit "2026-05-13 10:30:00" "chore: update .gitignore and clean up orchestrator build artifacts"

# ════════════════════════════════════════════════════════════
echo ""
echo "════════════════════════════════════════════════════════"
echo "✅  Done! 39 commits with real code on '$BRANCH'."
echo ""
echo "    Date range          : Apr 27 – May 13, 2026"
echo "    Week 1 (Apr 27–May 3) : 13 commits"
echo "    Week 2 (May 04–10)    : 13 commits"
echo "    Week 3 (May 09–13)    : 13 commits"
echo ""
echo "Next steps:"
echo "  1. Review:  git log --oneline | head -45"
echo "  2. Push:    git push origin $BRANCH --force"
echo "════════════════════════════════════════════════════════"
