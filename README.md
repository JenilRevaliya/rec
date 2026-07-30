# REC — Real-time Event Capture

**Autonomous AI Photography System** — DSLR/PTZ-tethered, person-detecting, quality-gated, selfie-matched event photography.

---

## Quick Start

```bash
cp .env.example .env   # Edit secrets
bash init.sh           # Start full stack
```

| Service | URL |
|---|---|
| API Gateway | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/docs |
| User Portal | http://localhost:3000 |
| MinIO Console | http://localhost:9001 |
| Grafana | http://localhost:3001 |

---

## Architecture

```
edge-node/          Python services — camera control, detection, PIS, orchestrator, IQG
cloud-api/          FastAPI + Celery — face embedding, clustering, REST API
portal/             Next.js — selfie-match user portal
shared/             Shared TypeScript types
docker/             Docker infra configs (postgres init, prometheus)
```

## Feature Backlog

107 atomic features tracked in `.agent/history/marathon/feature_list.json`.

```bash
node node_modules/tribunal-kit/.agent/scripts/marathon_harness.js status
node node_modules/tribunal-kit/.agent/scripts/marathon_harness.js session-start
```

## PRD

See [PRD.md](./PRD.md) for full system design.
