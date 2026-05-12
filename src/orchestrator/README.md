# Orchestrator Service

Central coordination service for the autonomous email outreach pipeline.

## Architecture

The orchestrator sits at the center of the microservices architecture, coordinating work between:
- **Planning Service** — generates outreach plans from ICP definitions
- **Sourcing Service** — discovers companies matching the plan
- **Prospecting Service** — enriches contacts at discovered companies
- **Messaging Service** — generates and sends personalized emails

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | /api/campaigns | Create a new campaign |
| GET | /api/campaigns | List all campaigns |
| GET | /api/campaigns/:id | Campaign detail |
| PATCH | /api/campaigns/:id | Pause/resume campaign |
| DELETE | /api/campaigns/:id | Cancel campaign |
| GET | /api/campaigns/:id/stats | Campaign metrics |
| GET | /api/campaigns/:id/prospects | List prospects |
| GET | /api/campaigns/:id/drafts | List email drafts |
| GET | /api/status | System overview |
| GET | /api/metrics | Internal metrics |
| GET | /health | Liveness check |

## Quick Start

```bash
cp .env.example .env
npm install
npm run dev
```

## Event Flow

```
POST /api/campaigns
  → publish plan.requested
    → consume plan.ready → publish sourcing.requested
      → consume sourcing.completed → publish prospecting.requested
        → consume prospecting.completed → publish messaging.requested
```
