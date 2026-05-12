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
