import { CampaignStatus, PipelineStage } from '../../shared/types';
import { PostgresClient } from './client';

/**
 * Postgres-backed campaign orchestration status — schema mirrors the illustrative table in
 * design_docs/orchestrator_service_role.md §2.1.
 *
 * `campaign_id` is the join key with Mongo `campaigns`.
 */

export interface CampaignStatusRow {
  campaign_id: string;
  status: CampaignStatus;
  current_stage: PipelineStage;
  plan_id: string | null;
  last_error: string | null;
  stage_detail: Record<string, unknown> | null;
  created_at: Date;
  updated_at: Date;
}

const SCHEMA_SQL = `
  CREATE TABLE IF NOT EXISTS campaign_status (
    campaign_id    TEXT PRIMARY KEY,
    status         TEXT NOT NULL,
    current_stage  TEXT NOT NULL,
    plan_id        TEXT,
    last_error     TEXT,
    stage_detail   JSONB,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
  );
  CREATE INDEX IF NOT EXISTS idx_campaign_status_status ON campaign_status(status);
  CREATE INDEX IF NOT EXISTS idx_campaign_status_updated_at ON campaign_status(updated_at DESC);
`;

export class CampaignStatusRepository {
  constructor(private readonly pg: PostgresClient) {}

  async ensureSchema(): Promise<void> {
    await this.pg.query(SCHEMA_SQL);
  }

  async insert(row: {
    campaign_id: string;
    status: CampaignStatus;
    current_stage: PipelineStage;
    plan_id?: string | null;
  }): Promise<void> {
    await this.pg.query(
      `INSERT INTO campaign_status (campaign_id, status, current_stage, plan_id)
       VALUES ($1, $2, $3, $4)
       ON CONFLICT (campaign_id) DO UPDATE
         SET status = EXCLUDED.status,
             current_stage = EXCLUDED.current_stage,
             plan_id = EXCLUDED.plan_id,
             updated_at = now()`,
      [row.campaign_id, row.status, row.current_stage, row.plan_id ?? null]
    );
  }

  async updateStage(
    campaign_id: string,
    status: CampaignStatus,
    current_stage: PipelineStage,
    plan_id?: string | null
  ): Promise<void> {
    if (plan_id !== undefined) {
      await this.pg.query(
        `UPDATE campaign_status
            SET status = $2, current_stage = $3, plan_id = $4, updated_at = now()
          WHERE campaign_id = $1`,
        [campaign_id, status, current_stage, plan_id]
      );
    } else {
      await this.pg.query(
        `UPDATE campaign_status
            SET status = $2, current_stage = $3, updated_at = now()
          WHERE campaign_id = $1`,
        [campaign_id, status, current_stage]
      );
    }
  }

  async setStatus(campaign_id: string, status: CampaignStatus): Promise<void> {
    await this.pg.query(
      `UPDATE campaign_status
          SET status = $2, updated_at = now()
        WHERE campaign_id = $1`,
      [campaign_id, status]
    );
  }

  async setLastError(campaign_id: string, last_error: string | null): Promise<void> {
    await this.pg.query(
      `UPDATE campaign_status
          SET last_error = $2, updated_at = now()
        WHERE campaign_id = $1`,
      [campaign_id, last_error]
    );
  }

  async find(campaign_id: string): Promise<CampaignStatusRow | null> {
    const { rows } = await this.pg.query<CampaignStatusRow>(
      `SELECT campaign_id, status, current_stage, plan_id, last_error,
              stage_detail, created_at, updated_at
         FROM campaign_status WHERE campaign_id = $1`,
      [campaign_id]
    );
    return rows[0] ?? null;
  }

  async list(): Promise<CampaignStatusRow[]> {
    const { rows } = await this.pg.query<CampaignStatusRow>(
      `SELECT campaign_id, status, current_stage, plan_id, last_error,
              stage_detail, created_at, updated_at
         FROM campaign_status ORDER BY updated_at DESC`
    );
    return rows;
  }

  async countByStatus(): Promise<Record<string, number>> {
    const { rows } = await this.pg.query<{ status: string; count: string }>(
      `SELECT status, COUNT(*)::text AS count FROM campaign_status GROUP BY status`
    );
    const out: Record<string, number> = {};
    for (const r of rows) out[r.status] = parseInt(r.count, 10);
    return out;
  }
}
