"""Tests for API endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """Test health check endpoint."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data


@pytest.mark.asyncio
async def test_root_endpoint(client: AsyncClient):
    """Test root endpoint."""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "ASR-NMT Service"


@pytest.mark.asyncio
async def test_languages_endpoint(client: AsyncClient):
    """Test languages listing endpoint."""
    response = await client.get("/v1/languages")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert all("code" in lang for lang in data)


@pytest.mark.asyncio
async def test_create_job_without_auth(client: AsyncClient):
    """Test job creation without authentication."""
    response = await client.post(
        "/v1/jobs",
        json={
            "job_type": "asr",
            "items": [{"audio_url": "http://example.com/audio.wav"}],
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_job_with_auth(client: AsyncClient, auth_headers: dict):
    """Test job creation with authentication."""
    response = await client.post(
        "/v1/jobs",
        headers=auth_headers,
        json={
            "job_type": "asr",
            "items": [
                {"id": "test-1", "audio_url": "http://example.com/audio.wav"},
            ],
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert "job_id" in data
    assert data["enqueued_tasks"] == 1


@pytest.mark.asyncio
async def test_create_nmt_job_requires_target_lang(
    client: AsyncClient, auth_headers: dict
):
    """Test NMT job requires target language."""
    response = await client.post(
        "/v1/jobs",
        headers=auth_headers,
        json={
            "job_type": "nmt",
            "items": [{"text": "Hello world"}],
        },
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_list_jobs(client: AsyncClient, auth_headers: dict):
    """Test job listing."""
    response = await client.get("/v1/jobs", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "jobs" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_get_nonexistent_job(client: AsyncClient, auth_headers: dict):
    """Test getting a job that doesn't exist."""
    response = await client.get(
        "/v1/jobs/00000000-0000-0000-0000-000000000000",
        headers=auth_headers,
    )
    assert response.status_code == 404
