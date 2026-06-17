"""Unit tests for the Ingestion API endpoints."""

from __future__ import annotations
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
import pytest

# We mock RabbitMQ before importing the app to avoid connection attempts during test setup
with patch("pika.BlockingConnection"):
    from services.ingestion_api.main import app

client = TestClient(app)


def test_health_check_disconnected():
    """Test health endpoint when broker is not connected."""
    response = client.get("/health")
    # Should be 503 because RabbitMQ is not actually running in CI
    assert response.status_code == 503


def test_ingest_valid_event():
    """Test that the API accepts valid mobile events."""
    payload = {
        "user_id": "test_user",
        "event_type": "transaction",
        "amount": 100.50,
        "device_id": "mobile_ios_12",
        "location": "45.0,9.0",
    }

    # Mock the publish method to avoid pika errors
    with patch("services.ingestion_api.main.rmq.publish") as mock_publish:
        response = client.post("/events", json=payload)
        assert response.status_code == 201
        assert response.json()["status"] == "accepted"
        mock_publish.assert_called_once()


def test_ingest_invalid_schema():
    """Test that the API rejects invalid data (Zero-Trust)."""
    invalid_payload = {
        "user_id": "test_user",
        "amount": "NOT_A_NUMBER",  # This should trigger a Pydantic error
    }
    response = client.post("/events", json=invalid_payload)
    assert response.status_code == 422  # Unprocessable Entity
