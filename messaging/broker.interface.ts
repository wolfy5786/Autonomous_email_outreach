export interface MessageBroker {
  publish(topic: string, message: unknown): Promise<void>;
  subscribe(topic: string, handler: (message: unknown) => Promise<void>): Promise<void>;
  disconnect(): Promise<void>;
}
