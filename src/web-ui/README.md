# email_outreach web UI

Operator UI for the email_outreach system — manage campaigns, review prospects,
approve drafts. Talks to the (not-yet-built) gateway service via a typed REST
client. In development, **MSW (Mock Service Worker)** intercepts requests and
returns seed data, so the UI runs end-to-end without any backend.

## Stack

- React 18 + TypeScript
- Vite 5
- Tailwind CSS 3 + shadcn/ui (Radix primitives)
- React Router 6
- TanStack Query 5
- MSW 2 (dev/test mocking)
- Vitest + Testing Library

## Develop

```bash
cd src/web
npm install
npm run dev         # http://localhost:5173 (MSW intercepts /api/*)
```

To point at a real backend instead of the mock:

```bash
VITE_API_BASE_URL=http://localhost:8000 npm run dev
```

## Build

```bash
npm run build       # outputs to dist/
npm run preview     # serve the production bundle locally
```

## Tests

```bash
npm test
```
