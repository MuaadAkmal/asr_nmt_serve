"""Initial migration

Revision ID: 001_initial
Revises: 
Create Date: 2026-01-31

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create api_keys table
    op.create_table(
        'api_keys',
        sa.Column('id', postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column('key_hash', sa.String(255), nullable=False, unique=True, index=True),
        sa.Column('key_prefix', sa.String(10), nullable=False, index=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('owner', sa.String(100), nullable=False),
        sa.Column('scopes', postgresql.JSON(), nullable=True, default=[]),
        sa.Column('rate_limit_per_minute', sa.Integer(), nullable=False, default=60),
        sa.Column('rate_limit_per_hour', sa.Integer(), nullable=False, default=500),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
    )

    # Create jobs table
    op.create_table(
        'jobs',
        sa.Column('id', postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column('api_key_id', postgresql.UUID(as_uuid=False), sa.ForeignKey('api_keys.id'), nullable=False, index=True),
        sa.Column('job_type', sa.Enum('asr', 'nmt', 'asr+nmt', name='jobtype'), nullable=False),
        sa.Column('status', sa.Enum('pending', 'processing', 'completed', 'failed', 'partial', name='jobstatus'), nullable=False, default='pending'),
        sa.Column('default_src_lang', sa.String(10), nullable=True),
        sa.Column('default_tgt_lang', sa.String(10), nullable=True),
        sa.Column('priority', sa.Integer(), nullable=False, default=5),
        sa.Column('total_tasks', sa.Integer(), nullable=False, default=0),
        sa.Column('completed_tasks', sa.Integer(), nullable=False, default=0),
        sa.Column('failed_tasks', sa.Integer(), nullable=False, default=0),
        sa.Column('metadata', postgresql.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    )

    # Create tasks table
    op.create_table(
        'tasks',
        sa.Column('id', postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column('job_id', postgresql.UUID(as_uuid=False), sa.ForeignKey('jobs.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('external_id', sa.String(100), nullable=True),
        sa.Column('input_type', sa.String(20), nullable=False),
        sa.Column('input_ref', sa.Text(), nullable=False),
        sa.Column('input_storage_path', sa.Text(), nullable=True),
        sa.Column('src_lang', sa.String(10), nullable=True),
        sa.Column('tgt_lang', sa.String(10), nullable=True),
        sa.Column('detected_lang', sa.String(10), nullable=True),
        sa.Column('status', sa.Enum('pending', 'queued', 'processing', 'completed', 'failed', 'retrying', name='taskstatus'), nullable=False, default='pending'),
        sa.Column('asr_model_used', sa.Enum('whisper', 'omni', name='asrmodel'), nullable=True),
        sa.Column('celery_task_id', sa.String(100), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, default=0),
        sa.Column('max_retries', sa.Integer(), nullable=False, default=3),
        sa.Column('asr_result', sa.Text(), nullable=True),
        sa.Column('nmt_result', sa.Text(), nullable=True),
        sa.Column('result_storage_path', sa.Text(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('processing_time_ms', sa.Integer(), nullable=True),
        sa.Column('audio_duration_ms', sa.Integer(), nullable=True),
    )

    # Create audit_logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column('api_key_id', postgresql.UUID(as_uuid=False), nullable=True, index=True),
        sa.Column('action', sa.String(50), nullable=False, index=True),
        sa.Column('resource_type', sa.String(50), nullable=False),
        sa.Column('resource_id', sa.String(100), nullable=True),
        sa.Column('details', postgresql.JSON(), nullable=True),
        sa.Column('ip_address', sa.String(50), nullable=True),
        sa.Column('user_agent', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Create indexes
    op.create_index('ix_jobs_status', 'jobs', ['status'])
    op.create_index('ix_jobs_created_at', 'jobs', ['created_at'])
    op.create_index('ix_tasks_status', 'tasks', ['status'])


def downgrade() -> None:
    op.drop_index('ix_tasks_status')
    op.drop_index('ix_jobs_created_at')
    op.drop_index('ix_jobs_status')
    op.drop_table('audit_logs')
    op.drop_table('tasks')
    op.drop_table('jobs')
    op.drop_table('api_keys')
    op.execute('DROP TYPE IF EXISTS taskstatus')
    op.execute('DROP TYPE IF EXISTS asrmodel')
    op.execute('DROP TYPE IF EXISTS jobstatus')
    op.execute('DROP TYPE IF EXISTS jobtype')
