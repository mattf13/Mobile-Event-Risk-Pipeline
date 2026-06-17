from __future__ import annotations
from shared.schemas import MobileEvent
from services.risk_scorer.main import RiskScorer


def test_high_amount_risk():
    """Test that amounts over 900 trigger a high risk score."""
    event = MobileEvent(
        user_id="user_1",
        event_type="transaction",
        amount=1200.0,
        device_id="dev_1",
        location="0,0",
    )
    # call RiskScorer class
    score, rationale = RiskScorer.analyze_risk_stage_1(event)
    assert score == 95
    assert "CRITICAL" in rationale


def test_low_amount_risk():
    """Test that standard transactions have a low score."""
    event = MobileEvent(
        user_id="user_1",
        event_type="transaction",
        amount=50.0,
        device_id="dev_1",
        location="0,0",
    )
    # call RiskScorer class
    score, _ = RiskScorer.analyze_risk_stage_1(event)
    assert score == 0


def test_login_base_risk():
    """Test that logins have a baseline risk score and logout does not."""
    # Test Login
    login_event = MobileEvent(
        user_id="user_1",
        event_type="login",
        amount=0.0,
        device_id="dev_1",
        location="0,0",
    )
    score, _ = RiskScorer.analyze_risk_stage_1(login_event)
    assert score == 10

    # Test Logout
    logout_event = MobileEvent(
        user_id="user_1",
        event_type="logout",
        amount=0.0,
        device_id="dev_1",
        location="0,0",
    )
    score, _ = RiskScorer.analyze_risk_stage_1(logout_event)
    assert score == 0
