# ASR-NMT Service

A production-grade **Automatic Speech Recognition (ASR)** and **Neural Machine Translation (NMT)** batch processing service built with FastAPI, Celery, and Redis.

## Features

- ✅ **Batch Processing**: Submit multiple audio files or text items in a single request
- ✅ **ASR**: Transcribe audio using OpenAI Whisper (primary) or FB Omni (fallback)
- ✅ **NMT**: Translate text between supported languages
- ✅ **ASR+NMT**: Combined transcription and translation pipeline
- ✅ **API Key Authentication**: Secure API access with scoped keys
- ✅ **Rate Limiting**: Per-key and global rate limits
- ✅ **Concurrent Processing**: Celery workers with configurable concurrency
- ✅ **Priority Queues**: Prioritize urgent jobs
- ✅ **Auto Language Detection**: Automatic source language detection
- ✅ **Job Tracking**: Track job and task progress in real-time

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

## API Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Client    │────▶│  FastAPI    │────▶│   Redis     │
│             │     │   (API)     │     │  (Queue)    │
└─────────────┘     └─────────────┘     └──────┬──────┘
                           │                    │
                           ▼                    ▼
                    ┌─────────────┐     ┌─────────────┐
                    │  PostgreSQL │     │   Celery    │
                    │    (DB)     │     │  Workers    │
                    └─────────────┘     └──────┬──────┘
                                               │
                    ┌─────────────┐            │
                    │   MinIO     │◀───────────┘
                    │ (Storage)   │
                    └─────────────┘
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

## License

MIT
