from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from research_agent.config import Settings
from research_agent.models import QuotaLedger


class QuotaExhausted(RuntimeError):
    pass


class QuotaManager:
    def __init__(self, settings: Settings):
        self.settings = settings

    def reserve(self, session: Session, model: str, estimated_tokens: int = 0) -> QuotaLedger:
        day = datetime.now(UTC).date().isoformat()
        statement = select(QuotaLedger).where(
            QuotaLedger.provider == "groq",
            QuotaLedger.model == model,
            QuotaLedger.day == day,
        )
        ledger = session.scalar(statement)
        if ledger is None:
            ledger = QuotaLedger(provider="groq", model=model, day=day)
            session.add(ledger)
            session.flush()

        request_limit = self.settings.groq_daily_request_limit
        if model == "groq/compound":
            request_limit = self.settings.compound_daily_search_limit

        if ledger.request_count >= request_limit:
            raise QuotaExhausted(f"Daily request limit reached for {model}")
        if ledger.token_count + estimated_tokens > self.settings.groq_daily_token_limit:
            raise QuotaExhausted(f"Daily token limit reached for {model}")

        ledger.request_count += 1
        ledger.token_count += estimated_tokens
        session.commit()
        return ledger

    def record_actual_tokens(
        self, session: Session, model: str, estimated_tokens: int, actual_tokens: int
    ) -> None:
        day = datetime.now(UTC).date().isoformat()
        statement = select(QuotaLedger).where(
            QuotaLedger.provider == "groq",
            QuotaLedger.model == model,
            QuotaLedger.day == day,
        )
        ledger = session.scalar(statement)
        if ledger is None:
            return
        ledger.token_count += actual_tokens - estimated_tokens
        session.commit()
