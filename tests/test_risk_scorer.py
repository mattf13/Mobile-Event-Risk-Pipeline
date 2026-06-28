"""Unit tests for the RiskScorer logic and AI integration."""

from __future__ import annotations
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


def test_stage_2_ai_integration_success():
    """Test that the AI stage correctly parses a valid JSON response from Groq."""
    event = MobileEvent(
        user_id="user_ai",
        event_type="transaction",
        amount=600.0,
        device_id="dev_123",
        location="0,0",
    )
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(
            message=MagicMock(
                content='{"score": 85, "rationale": "High value pattern"}'
            )
        )
    ]

    with patch(
        "openai.resources.chat.completions.Completions.create",
        return_value=mock_response,
    ):
        with patch.dict("os.environ", {"GROQ_API_KEY": "gsk_dummy"}):
            score, rationale = RiskScorer.analyze_risk_stage_2_llm(event)
            assert score == 85
            assert "AI_ANALYSIS" in rationale


def test_stage_2_ai_fallback_on_api_error():
    """Test that the system falls back to mock logic if the AI API fails."""
    event = MobileEvent(
        user_id="user_fail",
        event_type="transaction",
        amount=600.0,
        device_id="dev_normal",
        location="0,0",
    )
    with patch(
        "openai.resources.chat.completions.Completions.create",
        side_effect=Exception("API Error"),
    ):
        with patch.dict("os.environ", {"GROQ_API_KEY": "gsk_dummy"}):
            score, _ = RiskScorer.analyze_risk_stage_2_llm(event)
            assert score == 0  # Backs up to mock which returns 0 for dev_normal

def test_ai_score_clamping():
    """Test that LLM scores outside 0-100 range are correctly clamped."""
    # Mock a hallucinating LLM returning 150
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(
            message=MagicMock(content='{"score": 150, "rationale": "Extreme risk"}')
        )
    ]

    with patch(
        "openai.resources.chat.completions.Completions.create",
        return_value=mock_response,
    ):
        with patch.dict("os.environ", {"GROQ_API_KEY": "dummy"}):
            score, _ = RiskScorer.analyze_risk_stage_2_llm(MagicMock(spec=MobileEvent))
            assert score == 100  # Must be clamped to 100
