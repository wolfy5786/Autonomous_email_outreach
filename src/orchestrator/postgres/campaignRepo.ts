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
