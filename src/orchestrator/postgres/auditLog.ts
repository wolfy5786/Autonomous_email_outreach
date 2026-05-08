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
