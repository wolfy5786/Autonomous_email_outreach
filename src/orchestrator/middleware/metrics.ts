import { Request, Response, NextFunction } from 'express';

// Simple in-memory metrics (replace with prom-client in production)
const metrics = {
  httpRequestsTotal: 0,
  httpRequestsByRoute: {} as Record<string, number>,
  httpRequestsByStatus: {} as Record<string, number>,
  startTime: Date.now(),
};

export function metricsMiddleware(req: Request, res: Response, next: NextFunction): void {
  res.on('finish', () => {
    metrics.httpRequestsTotal++;
    const routeKey = `${req.method} ${req.route?.path || req.path}`;
    metrics.httpRequestsByRoute[routeKey] = (metrics.httpRequestsByRoute[routeKey] || 0) + 1;
    const statusKey = `${res.statusCode}`;
    metrics.httpRequestsByStatus[statusKey] = (metrics.httpRequestsByStatus[statusKey] || 0) + 1;
  });
  next();
}

export function getMetrics() {
  return {
    ...metrics,
    uptimeSeconds: Math.floor((Date.now() - metrics.startTime) / 1000),
  };
}
