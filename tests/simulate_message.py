from __future__ import annotations
import json
from unittest.mock import MagicMock
from services.risk_scorer.main import RiskScorer

def simulate_event():
    """Simulates a call to the consumer callback."""
    # Mocking RabbitMQ channel and method objects
    scorer = RiskScorer()
    mock_ch = MagicMock()
    mock_method = MagicMock()
    mock_method.delivery_tag = 1

    # Valid JSON payload
    valid_payload = json.dumps(
        {
            "user_id": "test_user",
            "event_type": "transaction",
            "amount": 999.99,
            "device_id": "test_device",
            "location": "46.49,11.33",
        }
    ).encode("utf-8")

    print("Simulating valid message processing...")
    scorer.on_message_received(mock_ch, mock_method, None, valid_payload)

    # Invalid JSON payload (Security Test)
    invalid_payload = b"invalid json data"
    print("\nSimulating malicious/invalid message processing...")
    scorer.on_message_received(mock_ch, mock_method, None, invalid_payload)


if __name__ == "__main__":
    simulate_event()
