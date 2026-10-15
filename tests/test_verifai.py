from datetime import date

import pytest
from pydantic import BaseModel

from verifai import (DataStatus, Sourced, Unverified, assess, confidence_of, seed, to_json,
                     unknown, value_of, walk)

TODAY = date(2026, 3, 1)


class Cafe(BaseModel):
    """A toy record: a cafe listing where every fact carries its source."""
    name: str
    opens_at: Sourced[str] = unknown()
    has_wifi: Sourced[bool] = unknown()
    price_of_coffee: Sourced[float] = unknown()


def verified(value, days_ago=0):
    return Sourced(value=value, status=DataStatus.VERIFIED, source_url="https://example.com/menu",
                   evidence="quoted text", verified_at=date.fromordinal(TODAY.toordinal() - days_ago))


def test_extracted_values_require_evidence():
    with pytest.raises(ValueError):
        Sourced(value=5.0, status=DataStatus.EXTRACTED, source_url="https://example.com")
    assert Sourced(value=5.0, status=DataStatus.EXTRACTED, evidence="coffee is 5.00").known


def test_verified_values_require_a_source_and_date():
    with pytest.raises(ValueError):
        Sourced(value=True, status=DataStatus.VERIFIED)


def test_unknown_is_never_guessed():
    assert value_of(unknown()) is None
    assert value_of(seed(3.5)) == 3.5


def test_require_refuses_unverified_and_stale_values():
    with pytest.raises(Unverified):
        seed("08:00").require()
    assert seed("08:00").require(at_least=DataStatus.UNVERIFIED_SEED) == "08:00"
    old = verified(True, days_ago=90)
    assert old.require() is True
    with pytest.raises(Unverified):
        old.require(max_age_days=30, today=TODAY)


def test_confidence_follows_provenance():
    assert confidence_of(verified(1), verified(2)) == 1.0
    assert confidence_of(verified(1), unknown()) == 0.5
    assert confidence_of() == 0.0


def test_walk_and_assess_a_whole_record():
    cafe = Cafe(name="Corner", opens_at=verified("07:30", days_ago=45), has_wifi=seed(True))
    assert len(list(walk(cafe))) == 3
    f = assess(cafe, stale_after_days=30, today=TODAY)
    assert (f.verified, f.unverified, f.unknown) == (1, 1, 1)
    assert f.stale and f.label == "stale"


def test_seed_data_never_claims_to_be_verified():
    """The guard to keep in your own suite: hand-entered data must not be marked verified."""
    dataset = [Cafe(name="A", opens_at=seed("08:00")), Cafe(name="B", has_wifi=seed(False))]
    assert not any(s.trustworthy for c in dataset for s in walk(c))


def test_json_always_carries_status():
    assert to_json(unknown()) == {"value": None, "status": "unknown"}
    out = to_json(verified(4.2))
    assert out["value"] == 4.2 and out["status"] == "verified" and out["source"]
