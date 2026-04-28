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
