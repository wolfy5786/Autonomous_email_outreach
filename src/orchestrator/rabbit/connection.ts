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
