# verifai

Values that carry their own evidence. Wrap any fact your code relies on in
`Sourced[T]`: the value, where it came from, a verbatim quote, and how far it
has been checked. Code that uses the fact can no longer avoid knowing how
much to trust it.

Built for systems where a wrong fact stated confidently is the worst
outcome: advisors, comparison sites, and anything that hands data to a
language model to talk about.

```python
from datetime import date
from verifai import Sourced, DataStatus, seed, unknown

price = Sourced(
    value=4.50,
    status=DataStatus.VERIFIED,
    source_url="https://example.com/menu",
    evidence="Flat white ... 4.50",
    verified_at=date(2026, 3, 1),
)
hours = seed("07:30")          # entered by hand, not yet checked
wifi = unknown()               # we genuinely don't know
```

## Trust is a type, not a convention

Every value has one of four statuses:

| Status | Meaning |
| --- | --- |
| `verified` | A person checked it against a live source. Needs a URL and a date. |
| `extracted` | Pulled automatically, by a scraper or a model. Needs a verbatim quote. |
| `unverified_seed` | Entered by hand. Never counts as verified. |
| `unknown` | We don't know, and we won't pretend to. |

What falls out of that:

- **Unknown is never guessed.** `value_of(s)` returns `None` for unknown
  values, so scoring code can exclude them instead of inventing a default.
- **Hard stops where they matter.** `s.require()` returns the value only if
  it is verified, and optionally fresh enough. Otherwise it raises
  `Unverified`. Use it anywhere a value would be shown to a user as fact.
- **Confidence propagates.** `confidence_of(a, b, c)` scores a conclusion
  from the provenance of the values behind it, so a well-documented option
  beats a poorly documented one on a tie.
- **Whole records can be audited.** `walk(record)` finds every `Sourced`
  value inside nested models, lists and dicts. `assess(record)` counts
  verified, unverified and unknown fields and flags stale ones.
- **Status travels with the value.** `to_json(s)` gives an API or LLM tool
  result the value together with its status, source and quote, so a model
  can say "unconfirmed" instead of stating it as fact.

## With a language model

Let the model converse and let code decide. Give the model tools that
return `to_json()` output, and in the system prompt tell it to mention the
status of anything it repeats. It can't claim a value is confirmed when the
tool result says otherwise.

## A test worth copying

```python
def test_seed_data_never_claims_to_be_verified():
    assert not any(s.trustworthy for record in DATASET for s in walk(record))
```

It fails the build if anyone marks hand-entered data as verified without
doing the work.

## Install and test

```
pip install git+https://github.com/withZion/verifai
pip install -e .[dev] && pytest
```

## License

MIT.
