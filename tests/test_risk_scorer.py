"""Unit tests for the RiskScorer logic."""

from __future__ import annotations
import json
from unittest.mock import patch, MagicMock
from shared.schemas import MobileEvent
from services.risk_scorer.main import RiskScorer


def test_high_amount_risk():
    """Test that amounts over 900 trigger a critical risk score."""
    event = MobileEvent(
        user_id="user_1",
        event_type="transaction",
        amount=1200.0,
        device_id="dev_1",
        location="0,0",
    )
    score, rationale = RiskScorer.analyze_risk_stage_1(event)
    assert score == 95
    assert "CRITICAL" in rationale


def test_login_base_risk():
    """Test that login events have a baseline risk and logouts do not."""
    login_event = MobileEvent(
        user_id="user_1",
        event_type="login",
        amount=0.0,
        device_id="dev_1",
        location="0,0",
    )
    score, _ = RiskScorer.analyze_risk_stage_1(login_event)
    assert score == 10

    logout_event = MobileEvent(
        user_id="user_1",
        event_type="logout",
        amount=0.0,
        device_id="dev_1",
        location="0,0",
    )
    score, _ = RiskScorer.analyze_risk_stage_1(logout_event)
    assert score == 0


def test_stage_2_llm_detection():
    """Test that Stage 2 (Mock LLM) identifies suspicious device IDs."""
    event = MobileEvent(
        user_id="user_bot",
        event_type="transaction",
        amount=10.0,
        device_id="device_999",  # Suspicious device
        location="0,0",
    )
    # Stage 1 would return 0 for this amount
    s1_score, _ = RiskScorer.analyze_risk_stage_1(event)
    assert s1_score == 0

    # Stage 2 should flag it
    llm_score, rationale = RiskScorer.analyze_risk_stage_2_mock_llm(event)
    assert llm_score == 85
    assert "LLM_REPORT" in rationale


def test_stage_2_llm_integration_success():
    """
    Test that on_message_received calls the LLM and processes its response.
    We mock the external API call to isolate the test.
    """
    scorer = RiskScorer()

    # Mocking RabbitMQ channel and method
    mock_ch = MagicMock()
    mock_method = MagicMock()
    mock_method.delivery_tag = 1

    # An event that will trigger the LLM call (amount > 500)
    event_payload = {
        "event_id": "test-llm-event-id",
        "user_id": "user_with_high_tx",
        "event_type": "transaction",
        "amount": 600.0,
        "device_id": "dev_normal",
        "location": "10,10",
    }
    event_body = json.dumps(event_payload).encode("utf-8")

    # Mocking the database to avoid real writes
    with patch.object(scorer.db_pool, "getconn") as mock_getconn:
        # Mocking the Mistral API call
        with patch("services.risk_scorer.main.Mistral") as mock_mistral:
            # Configure the mock to return a fake response
            mock_mistral.return_value.chat.complete.return_value = MagicMock(
                choices=[
                    MagicMock(
                        message=MagicMock(
                            content='{"score": 90, "reason": "AI detected unusual pattern."}'
                        )
                    )
                ]
            )

            # Call the function we want to test
            scorer.on_message_received(mock_ch, mock_method, None, event_body)

            #  ASSERTIONS 
            # call Mistral?
            mock_mistral.return_value.chat.complete.assert_called_once()

            # persist the LLM's score
            # Check what was sent to the DB
            insert_args = mock_getconn.return_value.cursor.return_value.__enter__.return_value.execute.call_args[
                0
            ][
                1
            ]
            persisted_score = insert_args[3]
            persisted_rationale = insert_args[5]

            assert persisted_score == 90
            assert "MISTRAL_AI: AI detected unusual pattern." in persisted_rationale
