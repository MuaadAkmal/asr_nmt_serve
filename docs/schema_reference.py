"""
Database Schema Reference
=========================

This file provides a quick reference for all database tables and columns.
For actual SQLAlchemy models, see: src/db/models.py

"""

# ============================================================================
# API_KEYS - Stores API keys for authentication
# ============================================================================
#
# | Column                | Type              | Constraints                    |
# |-----------------------|-------------------|--------------------------------|
# | id                    | UUID              | PRIMARY KEY                    |
# | key_hash              | VARCHAR(255)      | NOT NULL, UNIQUE, INDEX        |
# | key_prefix            | VARCHAR(10)       | NOT NULL, INDEX                |
# | name                  | VARCHAR(100)      | NOT NULL                       |
# | owner                 | VARCHAR(100)      | NOT NULL                       |
# | scopes                | JSON              | DEFAULT []                     |
# | rate_limit_per_minute | INTEGER           | NOT NULL, DEFAULT 60           |
# | rate_limit_per_hour   | INTEGER           | NOT NULL, DEFAULT 500          |
# | is_active             | BOOLEAN           | NOT NULL, DEFAULT TRUE         |
# | created_at            | TIMESTAMP(TZ)     | NOT NULL, DEFAULT now()        |
# | expires_at            | TIMESTAMP(TZ)     | NULLABLE                       |
#
# Relationships:
#   - jobs: ONE-TO-MANY -> jobs.api_key_id


# ============================================================================
# JOBS - Batch job containers
# ============================================================================
#
# | Column          | Type              | Constraints                        |
# |-----------------|-------------------|------------------------------------|
# | id              | UUID              | PRIMARY KEY                        |
# | api_key_id      | UUID              | NOT NULL, FK(api_keys.id), INDEX   |
# | job_type        | ENUM(JobType)     | NOT NULL                           |
# | status          | ENUM(JobStatus)   | NOT NULL, DEFAULT 'pending'        |
# | default_src_lang| VARCHAR(10)       | NULLABLE                           |
# | default_tgt_lang| VARCHAR(10)       | NULLABLE                           |
# | priority        | INTEGER           | NOT NULL, DEFAULT 5                |
# | total_tasks     | INTEGER           | NOT NULL, DEFAULT 0                |
# | completed_tasks | INTEGER           | NOT NULL, DEFAULT 0                |
# | failed_tasks    | INTEGER           | NOT NULL, DEFAULT 0                |
# | callback_url    | TEXT              | NULLABLE (webhook URL)             |
# | metadata        | JSON              | NULLABLE                           |
# | created_at      | TIMESTAMP(TZ)     | NOT NULL, DEFAULT now()            |
# | started_at      | TIMESTAMP(TZ)     | NULLABLE                           |
# | completed_at    | TIMESTAMP(TZ)     | NULLABLE                           |
#
# Enums:
#   JobType:   'asr' | 'nmt' | 'asr+nmt'
#   JobStatus: 'pending' | 'processing' | 'completed' | 'failed' | 'partial'
#
# Relationships:
#   - api_key: MANY-TO-ONE -> api_keys.id
#   - tasks:   ONE-TO-MANY -> tasks.job_id (CASCADE DELETE)



# ============================================================================
# TASKS - Individual processing units within a job
# ============================================================================
#
# | Column              | Type              | Constraints                    |
# |---------------------|-------------------|--------------------------------|
# | id                  | UUID              | PRIMARY KEY                    |
# | job_id              | UUID              | NOT NULL, FK(jobs.id), INDEX   |
# | external_id         | VARCHAR(100)      | NULLABLE (client-provided ID)  |
# | input_type          | VARCHAR(20)       | NOT NULL                       |
# | input_ref           | TEXT              | NOT NULL                       |
# | input_storage_path  | TEXT              | NULLABLE                       |
# | src_lang            | VARCHAR(10)       | NULLABLE                       |
# | tgt_lang            | VARCHAR(10)       | NULLABLE                       |
# | detected_lang       | VARCHAR(10)       | NULLABLE                       |
# | status              | ENUM(TaskStatus)  | NOT NULL, DEFAULT 'pending'    |
# | asr_model_used      | ENUM(ASRModel)    | NULLABLE                       |
# | celery_task_id      | VARCHAR(100)      | NULLABLE                       |
# | retry_count         | INTEGER           | NOT NULL, DEFAULT 0            |
# | max_retries         | INTEGER           | NOT NULL, DEFAULT 3            |
# | asr_result          | TEXT              | NULLABLE (transcribed text)    |
# | nmt_result          | TEXT              | NULLABLE (translated text)     |
# | result_storage_path | TEXT              | NULLABLE                       |
# | error_message       | TEXT              | NULLABLE                       |
# | created_at          | TIMESTAMP(TZ)     | NOT NULL, DEFAULT now()        |
# | started_at          | TIMESTAMP(TZ)     | NULLABLE                       |
# | completed_at        | TIMESTAMP(TZ)     | NULLABLE                       |
# | processing_time_ms  | INTEGER           | NULLABLE                       |
# | audio_duration_ms   | INTEGER           | NULLABLE                       |
#
# Enums:
#   TaskStatus: 'pending' | 'queued' | 'processing' | 'completed' | 'failed' | 'retrying'
#   ASRModel:   'whisper' | 'omni'
#
# Input Types:
#   'audio_url'  - URL to audio file
#   'audio_b64'  - Base64 encoded audio
#   'text'       - Plain text (for NMT-only jobs)
#
# Relationships:
#   - job: MANY-TO-ONE -> jobs.id


# ============================================================================
# AUDIT_LOGS - Track API usage and changes
# ============================================================================
#
# | Column        | Type              | Constraints                        |
# |---------------|-------------------|------------------------------------|
# | id            | UUID              | PRIMARY KEY                        |
# | api_key_id    | UUID              | NULLABLE, INDEX                    |
# | action        | VARCHAR(50)       | NOT NULL, INDEX                    |
# | resource_type | VARCHAR(50)       | NOT NULL                           |
# | resource_id   | VARCHAR(100)      | NULLABLE                           |
# | details       | JSON              | NULLABLE                           |
# | ip_address    | VARCHAR(50)       | NULLABLE                           |
# | user_agent    | VARCHAR(500)      | NULLABLE                           |
# | created_at    | TIMESTAMP(TZ)     | NOT NULL, DEFAULT now()            |
#
# Action Examples:
#   'job.create', 'job.complete', 'job.fail'
#   'task.start', 'task.complete', 'task.fail'
#   'api_key.create', 'api_key.revoke'


# ============================================================================
# INDEXES
# ============================================================================
#
# | Table    | Index Name          | Columns         |
# |----------|---------------------|-----------------|
# | api_keys | ix_api_keys_key_hash| key_hash        |
# | api_keys | ix_api_keys_prefix  | key_prefix      |
# | jobs     | ix_jobs_api_key_id  | api_key_id      |
# | jobs     | ix_jobs_status      | status          |
# | jobs     | ix_jobs_created_at  | created_at      |
# | tasks    | ix_tasks_job_id     | job_id          |
# | tasks    | ix_tasks_status     | status          |
# | audit    | ix_audit_api_key_id | api_key_id      |
# | audit    | ix_audit_action     | action          |


# ============================================================================
# SUPPORTED LANGUAGES
# ============================================================================
#
# | Code | Language   | Whisper | Omni | NMT |
# |------|------------|---------|------|-----|
# | en   | English    | ✓       | ✓    | ✓   |
# | hi   | Hindi      | ✓       | ✓    | ✓   |
# | kn   | Kannada    | ✓       | ✓    | ✓   |
# | mr   | Marathi    | ✓       | ✓    | ✓   |
# | te   | Telugu     | ✓       | ✓    | ✓   |
# | ml   | Malayalam  | ✓       | ✓    | ✓   |
# | ta   | Tamil      | ✓       | ✓    | ✓   |


# ============================================================================
# ER DIAGRAM (Text)
# ============================================================================
#
#  ┌──────────────┐
#  │   api_keys   │
#  ├──────────────┤
#  │ id (PK)      │───────────────────────┐
#  │ key_hash     │                       │
#  │ key_prefix   │                       │
#  │ name         │                       │
#  │ owner        │                       │
#  │ scopes       │                       │
#  │ rate_limits  │                       │
#  │ is_active    │                       │
#  │ created_at   │                       │
#  │ expires_at   │                       │
#  └──────────────┘                       │
#                                         │ 1:N
#  ┌──────────────┐                       │
#  │     jobs     │◄──────────────────────┘
#  ├──────────────┤
#  │ id (PK)      │───────────────────────┐
#  │ api_key_id   │ (FK)                  │
#  │ job_type     │                       │
#  │ status       │                       │
#  │ src_lang     │                       │
#  │ tgt_lang     │                       │
#  │ priority     │                       │
#  │ task_counts  │                       │
#  │ timestamps   │                       │
#  └──────────────┘                       │
#                                         │ 1:N
#  ┌──────────────┐                       │
#  │    tasks     │◄──────────────────────┘
#  ├──────────────┤
#  │ id (PK)      │
#  │ job_id (FK)  │
#  │ external_id  │
#  │ input_type   │
#  │ input_ref    │
#  │ languages    │
#  │ status       │
#  │ asr_model    │
#  │ results      │
#  │ error        │
#  │ timestamps   │
#  │ metrics      │
#  └──────────────┘
#
#  ┌──────────────┐
#  │  audit_logs  │
#  ├──────────────┤
#  │ id (PK)      │
#  │ api_key_id   │
#  │ action       │
#  │ resource     │
#  │ details      │
#  │ ip/ua        │
#  │ created_at   │
#  └──────────────┘
