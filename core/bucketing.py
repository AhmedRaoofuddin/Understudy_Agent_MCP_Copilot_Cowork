"""Risk bucketing: turn a loose proposal into a stable, dense tracking key.

If we tracked trust by raw task strings and raw payloads, the cells would
shatter into thousands of single sample buckets and nothing would ever earn
autonomy. Instead we collapse a proposal into a small set of risk dimensions:
the function domain, a normalized verb, a value tier, and an access scope. Many
real tasks map to the same bucket, so evidence accumulates and the trust math
can actually move.

The classifier fails closed. If a value looks present but cannot be parsed, or a
payload carries a money like field we were not told about, we assume the worst
tier rather than the safest. A high value action wrongly treated as low value is
the exact mistake that leads to a disaster, so we never make it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Tuple

VALUE_LOW = "LOW_VALUE"
VALUE_HIGH = "HIGH_VALUE"
VALUE_CRITICAL = "CRITICAL_VALUE"

ACCESS_INTERNAL = "INTERNAL"
ACCESS_EXTERNAL = "EXTERNAL"

_VALUE_RANK = {VALUE_LOW: 0, VALUE_HIGH: 1, VALUE_CRITICAL: 2}


def _default_verb_synonyms() -> Dict[str, str]:
    return {
        "UPDATE": "UPDATE",
        "MODIFY": "UPDATE",
        "ALTER": "UPDATE",
        "CHANGE": "UPDATE",
        "EDIT": "UPDATE",
        "SEND": "SEND",
        "DISPATCH": "SEND",
        "EMAIL": "SEND",
        "PAY": "PAY",
        "TRANSFER": "PAY",
        "CREATE": "CREATE",
        "ADD": "CREATE",
        "NEW": "CREATE",
        "DELETE": "DELETE",
        "REMOVE": "DELETE",
        "READ": "READ",
        "VIEW": "READ",
        "GET": "READ",
        "DECIDE": "DECIDE",
        "APPROVE_CANDIDATE": "DECIDE",
    }


@dataclass(frozen=True)
class BucketConfig:
    value_fields: Tuple[str, ...] = (
        "amount",
        "budget",
        "total_cost",
        "deal_value",
        "invoice_total",
        "payment_amount",
    )
    value_like_tokens: Tuple[str, ...] = (
        "amount",
        "value",
        "cost",
        "price",
        "total",
        "budget",
        "payment",
        "invoice",
    )
    access_fields: Tuple[str, ...] = (
        "destination",
        "recipient",
        "access_grant",
        "privilege",
        "security_tier",
        "channel",
        "share_scope",
    )
    access_like_tokens: Tuple[str, ...] = (
        "destination",
        "recipient",
        "external",
        "public",
        "grant",
        "privilege",
        "share",
    )
    external_markers: Tuple[str, ...] = (
        "external",
        "public",
        "admin",
        "root",
        "everyone",
        "anyone",
        "internet",
    )
    internal_markers: Tuple[str, ...] = (
        "internal",
        "team",
        "private",
        "colleague",
        "employee",
    )
    high_value_threshold: float = 10000.0
    critical_value_threshold: float = 100000.0
    verb_synonyms: Dict[str, str] = field(default_factory=_default_verb_synonyms)


@dataclass(frozen=True)
class Bucket:
    domain: str
    verb: str
    value_tier: str
    access_scope: str
    key: str
    failed_closed: bool


def _try_parse_amount(raw: Any) -> Tuple[bool, float]:
    text = str(raw).strip().replace(",", "").replace("$", "")
    try:
        return True, float(text)
    except (TypeError, ValueError):
        return False, 0.0


def _classify_value(payload: Mapping[str, Any], config: BucketConfig) -> Tuple[str, bool]:
    tier = VALUE_LOW
    ambiguous = False

    for field_name in config.value_fields:
        if field_name in payload:
            parsed_ok, amount = _try_parse_amount(payload[field_name])
            if not parsed_ok:
                ambiguous = True
                continue
            if amount >= config.critical_value_threshold:
                candidate = VALUE_CRITICAL
            elif amount >= config.high_value_threshold:
                candidate = VALUE_HIGH
            else:
                candidate = VALUE_LOW
            if _VALUE_RANK[candidate] > _VALUE_RANK[tier]:
                tier = candidate

    known = set(config.value_fields)
    for key in payload:
        if key in known:
            continue
        lowered = key.lower()
        if any(token in lowered for token in config.value_like_tokens):
            ambiguous = True

    if ambiguous:
        return VALUE_CRITICAL, True
    return tier, False


def _classify_access(payload: Mapping[str, Any], config: BucketConfig) -> Tuple[str, bool]:
    external = False
    ambiguous = False

    for field_name in config.access_fields:
        if field_name in payload:
            value_text = str(payload[field_name]).lower()
            if any(marker in value_text for marker in config.external_markers):
                external = True
            elif any(marker in value_text for marker in config.internal_markers):
                continue
            else:
                ambiguous = True

    known = set(config.access_fields)
    for key in payload:
        if key in known:
            continue
        lowered = key.lower()
        if any(token in lowered for token in config.access_like_tokens):
            ambiguous = True

    if external or ambiguous:
        return ACCESS_EXTERNAL, ambiguous
    return ACCESS_INTERNAL, False


def classify(
    domain: str, verb: str, payload: Mapping[str, Any], config: BucketConfig
) -> Bucket:
    normalized_domain = domain.strip().upper()
    raw_verb = verb.strip().upper()
    normalized_verb = config.verb_synonyms.get(raw_verb, raw_verb)

    value_tier, value_failed_closed = _classify_value(payload, config)
    access_scope, access_failed_closed = _classify_access(payload, config)

    key = ":".join([normalized_domain, normalized_verb, value_tier, access_scope])
    return Bucket(
        domain=normalized_domain,
        verb=normalized_verb,
        value_tier=value_tier,
        access_scope=access_scope,
        key=key,
        failed_closed=value_failed_closed or access_failed_closed,
    )


def bucket_from_key(key: str) -> Bucket:
    """Rebuild a Bucket from a stored key, for reporting over the event log."""
    parts = (key.split(":") + ["", "", "", ""])[:4]
    domain, verb, value_tier, access_scope = parts
    return Bucket(domain, verb, value_tier, access_scope, key, False)
