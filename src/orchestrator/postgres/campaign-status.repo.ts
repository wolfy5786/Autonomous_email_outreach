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
