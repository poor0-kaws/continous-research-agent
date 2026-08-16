import pytest

from research_agent.config import Settings
from research_agent.models import QuotaLedger
from research_agent.quota import QuotaExhausted, QuotaManager


def test_exhausted_free_quota_stops_before_a_model_call(session) -> None:  # type: ignore[no-untyped-def]
    settings = Settings(
        database_url="sqlite://",
        compound_daily_search_limit=0,
    )
    manager = QuotaManager(settings)

    with pytest.raises(QuotaExhausted, match="Daily request limit"):
        manager.reserve(session, "groq/compound", estimated_tokens=1_000)

    ledger = session.query(QuotaLedger).one()
    assert ledger.request_count == 0
    assert ledger.token_count == 0
