export interface QueueMessage<T = unknown> {
  eventType: string;
  payload: T;
  timestamp: string;
  correlationId: string;
}
