"""Unit tests for the RiskScorer logic."""

from __future__ import annotations
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
