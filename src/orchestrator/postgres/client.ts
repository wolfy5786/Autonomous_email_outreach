import { Pool, PoolClient } from 'pg';

/**
 * PostgreSQL pool wrapper for the Orchestrator.
 *
 * Backs per-`campaign_id` orchestration status — see design_docs/orchestrator_service_role.md §2.1.
 * Mongo continues to hold full campaign documents; Postgres answers "what stage?" cheaply.
 */
export class PostgresClient {
  private pool: Pool;

  constructor(connectionString: string) {
    this.pool = new Pool({ connectionString });
  }

  async connect(): Promise<void> {
    const c = await this.pool.connect();
    c.release();
  }

  async withClient<T>(fn: (client: PoolClient) => Promise<T>): Promise<T> {
    const c = await this.pool.connect();
    try {
      return await fn(c);
    } finally {
      c.release();
    }
  }

  async query<T = unknown>(
    text: string,
    values?: ReadonlyArray<unknown>
  ): Promise<{ rows: T[]; rowCount: number | null }> {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const res = await this.pool.query<any>(text, values as unknown[]);
    return { rows: res.rows as T[], rowCount: res.rowCount };
  }

  async disconnect(): Promise<void> {
    await this.pool.end();
  }
}
