# ADR-0014: Re-scaffold the frontend on Vite + TypeScript + Tailwind, with shadcn/ui components

- **Status:** Accepted
- **Date:** 2026-11-11
- **Change:** `improve-forecasting-evaluation-and-inventory`
- **Refines:** design.md decision 14; ADR-0013 (frontend test runner)

## Context

The owner wants shadcn/ui as the component library. The frontend is Create React App (`react-scripts` 5.0.1), plain JavaScript, hand-written CSS (`App.css`), Recharts, and a 328-line `App.js`. shadcn needs Tailwind CSS and an `@/` import alias. CRA hides its PostCSS and webpack config, so both need CRACO or `eject`. CRA was deprecated by the React team in 2025. The uncommitted `overrides` block in `package.json` exists only to patch vulnerable transitive dependencies of `react-scripts`. This change already splits `App.js` into components (forecast chart, accuracy panel, inventory panel), so most UI code is being rewritten regardless.

## Decision

- **Scaffold a new Vite + React + TypeScript app** in `frontend/` and port to it. Do not migrate the CRA app in place. Remove `react-scripts`, the `overrides` block, `eslintConfig` and `browserslist`.
- **Tailwind CSS v4** via `@tailwindcss/vite`, and **shadcn/ui** initialised per its Vite guide (`components.json`, `@/` alias in `tsconfig` and `vite.config.ts`). The hand-written CSS is replaced by Tailwind and shadcn tokens.
- **Charts use shadcn's Chart component** (a Recharts wrapper), keeping Recharts. Recharts is upgraded to the version that component targets.
- **Components used:** Select (product), Input and Slider (horizon, lead time, service level, on-hand), Button, Card (panels), Table (metrics, ablation), Badge (verdicts, risk level, config source), Alert (stale, not evaluated, `worse` verdict, errors), Skeleton (loading), Tabs (accuracy buckets), Tooltip (metric definitions taken from `CONTEXT.md`).
- **Dev server** keeps port 3000 and proxies `/api` to `localhost:5000` via `server.proxy`. `npm start` is kept as an alias for `vite` so existing docs and muscle memory still work. `axios` is dropped in favour of a small typed `fetch` client.
- **Tests:** Vitest + jsdom + `@testing-library/react` replace CRA's Jest (amends ADR-0013).
- **Docker:** the frontend image builds with `vite build` and serves `dist/` with nginx, proxying `/api` to the backend.

## Alternatives considered

- **Keep CRA and add CRACO for Tailwind and aliases:** fights deprecated tooling and keeps the vulnerable dependency tree.
- **Migrate CRA → Vite in place, then add shadcn:** two migrations of code that task 7 rewrites anyway.
- **Next.js / React Router framework mode:** server rendering and a Node server bring nothing to a single-page dashboard backed by Flask.
- **Stay on JavaScript:** shadcn supports `tsx: false`, but its docs and examples are TypeScript, and typed API response shapes help with the breaking API changes in this change. Owner confirmed TypeScript on 2026-11-11.

## Consequences

- API response types (`ForecastRun`, `Accuracy`, `InventoryRecommendation`) are written by hand in `frontend/src/api/types.ts` and must track the backend specs.
- shadcn components are copied into `frontend/src/components/ui/` and owned by the repo (that is shadcn's model), so they are reviewed like our own code.
- README, QUICKSTART, `setup.sh` and CLAUDE.md change "Frontend: ReactJS" / CRA instructions to Vite. Ports are unchanged.
