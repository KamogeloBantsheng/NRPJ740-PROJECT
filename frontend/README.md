# Web client

React, TypeScript and Vite. Setup for the whole system is in the root `README.md`.

| Command | Purpose |
|---|---|
| `npm run dev` | Dev server on port 5173, proxying `/api` to Django on port 8000 |
| `npm run build` | Type check and production build |
| `npm run lint` | ESLint |
| `npm test` | Unit tests (Vitest) |
| `npm run test:e2e` | Browser journeys (Playwright) against the stack on port 8080 |
| `npm run generate-api-types` | Regenerate `src/api/schema.d.ts` from `docs/openapi.yaml` |
