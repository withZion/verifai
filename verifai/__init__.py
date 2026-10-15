"""verifai: values that carry their own evidence.

Wrap any fact your system relies on in `Sourced[T]`: the value, where it
came from, a verbatim quote, and how far it has been checked. Then code that
uses the fact cannot avoid knowing how much to trust it.
"""
from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Any, Generic, Iterable, Optional, TypeVar

from pydantic import BaseModel, Field, model_validator

T = TypeVar("T")

__all__ = [
    "DataStatus", "Sourced", "Unverified", "seed", "unknown", "value_of", "cite",
    "confidence_of", "walk", "Freshness", "assess", "to_json",
]
__version__ = "0.1.0"


class DataStatus(str, Enum):
    """How much a value can be trusted."""
    VERIFIED = "verified"                # a person checked it against a live source
    EXTRACTED = "extracted"              # pulled automatically (scraper, LLM), awaiting review
    UNVERIFIED_SEED = "unverified_seed"  # entered by hand, not yet checked
    UNKNOWN = "unknown"                  # we genuinely do not know


WEIGHTS = {
    DataStatus.VERIFIED: 1.0,
    DataStatus.EXTRACTED: 0.75,
    DataStatus.UNVERIFIED_SEED: 0.5,
    DataStatus.UNKNOWN: 0.0,
}


class Unverified(LookupError):
    """Raised by `Sourced.require()` when a value is not trustworthy enough."""


class Sourced(BaseModel, Generic[T]):
    """A value plus the evidence for it."""
    value: Optional[T] = None
    status: DataStatus = DataStatus.UNKNOWN
    source_url: Optional[str] = None
    evidence: Optional[str] = Field(
        default=None, description="Verbatim quote from the source. Required for extracted values.")
    verified_at: Optional[date] = None
    note: Optional[str] = None

    @model_validator(mode="after")
    def _rules(self):
        if self.status == DataStatus.EXTRACTED and not self.evidence:
            raise ValueError("extracted values must carry verbatim evidence")
        if self.status == DataStatus.VERIFIED and not (self.source_url and self.verified_at):
            raise ValueError("verified values need a source_url and a verified_at date")
        return self

    @property
    def known(self) -> bool:
        return self.value is not None and self.status != DataStatus.UNKNOWN

    @property
    def trustworthy(self) -> bool:
        return self.status == DataStatus.VERIFIED

    def days_old(self, today: Optional[date] = None) -> Optional[int]:
        if not self.verified_at:
            return None
        return ((today or date.today()) - self.verified_at).days

    def require(self, at_least: DataStatus = DataStatus.VERIFIED,
                max_age_days: Optional[int] = None, today: Optional[date] = None) -> T:
        """Return the value only if it meets the bar; raise `Unverified` otherwise.

        Use this wherever a wrong value would be stated to a user as fact.
        """
        if not self.known or WEIGHTS[self.status] < WEIGHTS[at_least]:
            raise Unverified(f"value is {self.status.value}, need {at_least.value}")
        if max_age_days is not None:
            age = self.days_old(today)
            if age is None or age > max_age_days:
                raise Unverified(f"value last verified {age} days ago, limit {max_age_days}")
        return self.value  # type: ignore[return-value]


def seed(value: Any, url: str | None = None, note: str | None = None) -> Sourced:
    """Hand-entered data. Deliberately NOT marked verified."""
    return Sourced(value=value, status=DataStatus.UNVERIFIED_SEED, source_url=url, note=note)


def unknown() -> Sourced:
    return Sourced(status=DataStatus.UNKNOWN)


def value_of(s: Optional[Sourced]) -> Any:
    """The value, or None if we do not actually know it. Never a guess."""
    return s.value if s is not None and s.known else None


def cite(s: Optional[Sourced]) -> dict:
    """Provenance to attach to whatever conclusion used this value."""
    if s is None:
        return {}
    return {"evidence": s.evidence, "source_url": s.source_url}


def confidence_of(*sourced: Optional[Sourced]) -> float:
    """How far to trust a conclusion built from these values: 0.0 to 1.0."""
    vals = [WEIGHTS.get(s.status, 0.0) for s in sourced if s is not None]
    return sum(vals) / len(vals) if vals else 0.0


def walk(obj: Any, _depth: int = 0) -> Iterable[Sourced]:
    """Yield every Sourced value nested anywhere in a model, list or dict."""
    if _depth > 16:
        return
    if isinstance(obj, Sourced):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from walk(v, _depth + 1)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from walk(v, _depth + 1)
    elif isinstance(obj, BaseModel):
        for name in type(obj).model_fields:
            yield from walk(getattr(obj, name, None), _depth + 1)


class Freshness(BaseModel):
    verified: int = 0
    unverified: int = 0
    unknown: int = 0
    oldest_days: Optional[int] = None
    stale: bool = False

    @property
    def label(self) -> str:
        if not self.verified:
            return "unverified"
        if self.stale:
            return "stale"
        return "current"


def assess(obj: Any, stale_after_days: int = 30, today: Optional[date] = None) -> Freshness:
    """Count how much of a record is verified, and whether any of it is stale."""
    f = Freshness()
    ages = []
    for s in walk(obj):
        if s.status == DataStatus.VERIFIED:
            f.verified += 1
            age = s.days_old(today)
            if age is not None:
                ages.append(age)
        elif s.status == DataStatus.UNKNOWN:
            f.unknown += 1
        else:
            f.unverified += 1
    f.oldest_days = max(ages) if ages else None
    f.stale = f.oldest_days is not None and f.oldest_days > stale_after_days
    return f


def to_json(s: Optional[Sourced]) -> dict:
    """A compact dict for APIs or LLM tool results: the value never travels without its status."""
    if s is None or not s.known:
        return {"value": None, "status": "unknown"}
    val = s.value
    if isinstance(val, Enum):
        val = val.value
    elif hasattr(val, "model_dump"):
        val = val.model_dump()
    return {
        "value": val,
        "status": s.status.value,
        "source": s.source_url,
        "evidence": s.evidence,
        "verified_at": s.verified_at.isoformat() if s.verified_at else None,
    }
