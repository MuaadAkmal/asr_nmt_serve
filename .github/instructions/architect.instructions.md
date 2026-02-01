---
applyTo: '**'
---
High level architecture

FastAPI HTTP API (ingress) — accepts batch requests and returns a job id immediately.
Auth layer — API keys (or JWT) validated per request.
Rate limiter — Redis-backed token bucket / request quota.
Job queue — Celery (Redis broker, Redis or Postgres results) for background processing of tasks and batching.
Workers — Celery workers running model inference (use process pools for CPU-bound work) with per-model concurrency semaphores.
Storage — MinIO (S3 compatible) or local FS for audio/artifacts; Postgres for job metadata.
Models —
Primary ASR: OpenAI Whisper (local or containerized) for eng/hindi/tamil/... (flags for language & detect).
Fallback ASR: FB Omni for rare languages.
NMT: Marian, OpenNMT or a local transformer model; optionally call an external text translation service.
Monitoring / Observability — Prometheus + Grafana, centralized logs, Sentry for errors.
Core concepts

Job: container for a batch. A job has many tasks (each task = one input audio or text item).
Job types: asr, nmt, asr+nmt.
Batch: client sends many items in one request; server enqueues tasks; workers can process tasks in sub‑batches for efficiency.
Language selection: client may provide src_lng; if missing, use whisper language_detection mode.
Concurrency: global worker concurrency (celery worker pool) + per-model semaphore to avoid OOM and CPU contention.
Rate limiting: per API key and per route.
API specification (high-level)

POST /v1/jobs
headers: Authorization: Bearer <API_KEY>
body: { job_type: "asr"|"nmt"|"asr+nmt", items: [ { id:, audio_url: | base64:, src_lng?:, tgt_lng?: } ], default_src_lng?, default_tgt_lng?, priority? }
returns: { job_id, enqueued_tasks }
GET /v1/jobs/{job_id}
returns job metadata, status, progress, per-item results URLs.
GET /v1/jobs/{job_id}/results (or signed URLs)
POST /v1/auth/token (optional) — issue API key (admin-only)
GET /v1/health
Data model (Postgres)

api_keys (key, owner, rate_quota, scopes, created_at)
jobs (id, owner_key, job_type, status, created_at, updated_at, metadata JSON)
tasks (id, job_id, input_ref, status, result_ref, error, model_used, start_at, end_at)
audit logs