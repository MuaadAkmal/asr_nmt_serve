# ASR-NMT Service

A production-grade **Automatic Speech Recognition (ASR)** and **Neural Machine Translation (NMT)** batch processing service built with FastAPI, Celery, and Redis.

## Features

- ✅ **Batch Processing**: Submit multiple audio files or text items in a single request
- ✅ **ASR**: Transcribe audio using OpenAI Whisper (large-v3)
- ✅ **NMT**: Translate text using IndicTrans2 models with IndicTransToolkit
- ✅ **ASR+NMT**: Combined transcription and translation pipeline
- ✅ **Presigned Uploads**: Direct file upload to MinIO/S3 via presigned URLs
- ✅ **Webhooks**: Receive callbacks when jobs complete
- ✅ **API Key Authentication**: Secure API access with scoped keys
- ✅ **Rate Limiting**: Per-key and global rate limits
- ✅ **Concurrent Processing**: Celery workers with configurable concurrency
- ✅ **Priority Queues**: Prioritize urgent jobs
- ✅ **Auto Language Detection**: Automatic source language detection
- ✅ **Job Tracking**: Track job and task progress in real-time
- ✅ **Kubernetes Ready**: Full K8s manifests with GPU node scheduling

## Supported Languages

| Code | Language   | ASR | NMT |
|------|------------|-----|-----|
| en   | English    | ✅  | ✅  |
| hi   | Hindi      | ✅  | ✅  |
| kn   | Kannada    | ✅  | ✅  |
| mr   | Marathi    | ✅  | ✅  |
| te   | Telugu     | ✅  | ✅  |
| ml   | Malayalam  | ✅  | ✅  |
| ta   | Tamil      | ✅  | ✅  |

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.10+ (for local development)
- NVIDIA GPU (optional, for faster inference)

### 1. Start with Docker Compose

```bash
# Clone and navigate to the project
cd serve

# Copy environment file
copy .env.example .env

# Start all services
docker-compose up -d

# Check logs
docker-compose logs -f api
```

### 2. Create an API Key

```bash
# Using the script
python scripts/create_admin_key.py

# Or via API (requires admin key in .env)
curl -X POST http://localhost:8000/v1/admin/api-keys \
  -H "X-Admin-Key: your-secret-key" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My App",
    "owner": "developer",
    "scopes": ["asr", "nmt", "asr+nmt"]
  }'
```

### 3. Submit a Job

```bash
# ASR Job (transcription only)
curl -X POST http://localhost:8000/v1/jobs \
  -H "Authorization: Bearer ask_your_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{
    "job_type": "asr",
    "items": [
      {"id": "audio-1", "audio_url": "https://example.com/audio.wav"}
    ],
    "default_src_lang": "en"
  }'

# ASR+NMT Job (transcription + translation)
curl -X POST http://localhost:8000/v1/jobs \
  -H "Authorization: Bearer ask_your_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{
    "job_type": "asr+nmt",
    "items": [
      {"id": "audio-1", "audio_url": "https://example.com/hindi-audio.wav"}
    ],
    "default_src_lang": "hi",
    "default_tgt_lang": "en"
  }'

# NMT Job (translation only)
curl -X POST http://localhost:8000/v1/jobs \
  -H "Authorization: Bearer ask_your_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{
    "job_type": "nmt",
    "items": [
      {"id": "text-1", "text": "Hello, how are you?"}
    ],
    "default_src_lang": "en",
    "default_tgt_lang": "hi"
  }'
```

### 4. Check Job Status

```bash
curl http://localhost:8000/v1/jobs/{job_id} \
  -H "Authorization: Bearer ask_your_api_key_here"
```

## Presigned Upload Flow

For large audio files, upload directly to MinIO/S3 using presigned URLs:

```bash
# Step 1: Get presigned upload URLs
curl -X POST http://localhost:8000/v1/jobs/upload-urls \
  -H "Authorization: Bearer ask_your_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{
    "count": 2,
    "content_type": "audio/wav",
    "expires_in": 3600
  }'
# Returns: { "job_id": "abc-123", "uploads": [{ "task_id": "...", "upload_url": "...", "storage_path": "..." }] }

# Step 2: Upload files directly to MinIO (using the upload_url from response)
curl -X PUT "https://minio:9000/presigned-url-here" \
  -H "Content-Type: audio/wav" \
  --data-binary @audio1.wav

# Step 3: Confirm uploads and start processing
curl -X POST http://localhost:8000/v1/jobs/{job_id}/confirm \
  -H "Authorization: Bearer ask_your_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{
    "job_type": "asr",
    "items": [
      {"storage_path": "jobs/abc-123/tasks/task-id/input.wav"}
    ],
    "default_src_lang": "en"
  }'
```

## Webhooks

Get notified when jobs complete by providing a `callback_url`:

```bash
curl -X POST http://localhost:8000/v1/jobs \
  -H "Authorization: Bearer ask_your_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{
    "job_type": "asr",
    "items": [{"audio_url": "https://example.com/audio.wav"}],
    "callback_url": "https://your-server.com/webhook"
  }'
```

When the job completes, your webhook receives:

```json
{
  "event": "job.completed",
  "job_id": "job-uuid",
  "status": "completed",
  "total_tasks": 5,
  "completed_tasks": 5,
  "failed_tasks": 0,
  "completed_at": "2026-02-01T12:00:00Z"
}
```

## API Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/jobs` | POST | Create a new batch job |
| `/v1/jobs` | GET | List all jobs (paginated) |
| `/v1/jobs/{job_id}` | GET | Get job status and results |
| `/v1/jobs/{job_id}` | DELETE | Cancel/delete a job |
| `/v1/jobs/{job_id}/results` | GET | Get consolidated results |
| `/v1/jobs/upload-urls` | POST | Get presigned upload URLs |
| `/v1/jobs/{job_id}/confirm` | POST | Confirm uploads and start job |
| `/v1/admin/api-keys` | POST | Create API key (admin) |
| `/v1/admin/api-keys` | GET | List API keys (admin) |
| `/v1/health` | GET | Health check |

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Client    │────▶│  FastAPI    │────▶│   Redis     │
│             │     │   (API)     │     │  (Queue)    │
└─────────────┘     └─────────────┘     └──────┬──────┘
       │                   │                    │
       │                   ▼                    ▼
       │            ┌─────────────┐     ┌─────────────┐
       │            │  PostgreSQL │     │   Celery    │
       │            │    (DB)     │     │  Workers    │
       │            └─────────────┘     └──────┬──────┘
       │                                       │
       │  (presigned)  ┌─────────────┐         │
       └──────────────▶│   MinIO     │◀────────┘
                       │ (Storage)   │
                       └─────────────┘
```

### Task Flow

```
POST /v1/jobs ─────▶ API validates & creates job/tasks in DB
                              │
                              ▼
                     Enqueue tasks to Celery (Redis)
                              │
                              ▼
                     Workers pick up tasks
                              │
                    ┌─────────┴─────────┐
                    ▼                   ▼
               ASR (Whisper)      NMT (IndicTrans2)
                    │                   │
                    └─────────┬─────────┘
                              ▼
                     Update DB with results
                              │
                              ▼
                     If job complete → Send Webhook
```

## Configuration

| Environment Variable     | Description                          | Default              |
|-------------------------|--------------------------------------|----------------------|
| `DATABASE_URL`          | PostgreSQL connection URL            | `postgresql+asyncpg://...` |
| `REDIS_URL`             | Redis connection URL                 | `redis://localhost:6379/0` |
| `MINIO_ENDPOINT`        | MinIO/S3 endpoint                    | `localhost:9000`     |
| `WHISPER_MODEL_SIZE`    | Whisper model size                   | `large-v3`           |
| `WHISPER_DEVICE`        | Device for Whisper (`cuda`/`cpu`)    | `cuda`               |
| `WHISPER_CONCURRENCY`   | Max concurrent Whisper tasks         | `2`                  |
| `RATE_LIMIT_PER_MINUTE` | Default rate limit per minute        | `60`                 |

See `.env.example` for all configuration options.

## Development

### Local Setup

```bash
# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -e ".[dev]"

# Start dependencies
docker-compose up -d redis postgres minio

# Run migrations
alembic upgrade head

# Create admin key
python scripts/create_admin_key.py

# Start API server
uvicorn src.main:app --reload

# Start Celery worker (in another terminal)
celery -A src.worker worker --loglevel=info
```

### Running Tests

```bash
pytest tests/ -v
```

## Monitoring

- **Celery Flower**: http://localhost:5555 (task monitoring)
- **MinIO Console**: http://localhost:9001 (storage)

## Kubernetes Deployment

Deploy to a Kubernetes cluster with GPU support:

```bash
# Label GPU nodes
kubectl label nodes <gpu-node-1> gpu=true
kubectl label nodes <gpu-node-2> gpu=true

# Deploy
kubectl apply -k k8s/
```

### Cluster Architecture

| Component | Nodes | Replicas |
|-----------|-------|----------|
| API | Non-GPU | 2 (HPA: 2-6) |
| GPU Workers | GPU nodes (`gpu=true`) | 2 |
| CPU Workers | Non-GPU | 2 (HPA: 1-4) |
| Celery Beat | Non-GPU | 1 |
| PostgreSQL | Any | 1 |
| Redis | Any | 1 |
| MinIO | Any | 1 |

See [k8s/README.md](k8s/README.md) for detailed deployment instructions.

## Models

### ASR: OpenAI Whisper
- Model: `large-v3`
- Languages: All supported languages
- Device: CUDA (GPU) or CPU

### NMT: IndicTrans2
- Models:
  - `ai4bharat/indictrans2-en-indic-1B` (English → Indic)
  - `ai4bharat/indictrans2-indic-en-1B` (Indic → English)
  - `ai4bharat/indictrans2-indic-indic-1B` (Indic → Indic)
- Preprocessing: IndicTransToolkit with IndicProcessor
- Languages: en, hi, kn, mr, te, ml, ta

## License

MIT
