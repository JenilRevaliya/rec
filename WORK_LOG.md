# Marathon Session 1 Progress Log

## Completed Features

### ✅ Feature #1: Monorepo scaffold
- Created `package.json` for `edge-node`, `cloud-api`, `portal`, `shared`.
- Updated root workspace config to include all sub-projects.

### ✅ Feature #2: Docker Compose Configured
- Verified `docker-compose.yml` has all 9 target services.
- Removed obsolete syntax and configured environment templates (`.env`).

### ✅ Feature #3: Postgres + pgvector Setup
- Successfully started PostgreSQL container.
- Initialized schema with all 6 tables (`events`, `cameras`, `images`, `face_clusters`, `face_embeddings`, `portal_users`).
- Verified `pgvector` and `uuid-ossp` extensions loaded successfully.

### ✅ Feature #4: MinIO Object Storage Setup
- Started MinIO container and `minio-setup` script.
- Verified auto-creation of `rec-images` bucket on initialization.

## Currently In Progress

### ⏳ Feature #5: Celery Worker & Redis
- Created `cloud-api/Dockerfile`, `edge-node/Dockerfile`, and `portal/Dockerfile`.
- Set up initial Celery app (`cloud-api/tasks/celery_app.py`).
- Adjusted dependencies for cross-platform compatibility (`onnxruntime` instead of `-gpu`).
- *Status*: Building the `embedding-worker` Python environment (currently installing heavy data science packages like `insightface`). Once the build completes, the worker will be pinged via `celery inspect ping`.

## Pending Next
- Verify Celery worker connects to Redis successfully.
- Move onto Feature #6 (Monorepo routing and API Gateway setup).
