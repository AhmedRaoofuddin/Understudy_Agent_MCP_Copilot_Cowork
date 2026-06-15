"""Concurrency primitives so agent memory behaves like a distributed system.

The quiet failure in a multi agent system is shared mutable state. Several
agents, and several task runs at once, read a value, change it, and write it
back, silently clobbering each other. That is a lost update. It hides in single
threaded tests and only appears under real load.

This module provides the tools to avoid that:

  canonical_json and idempotency_key give stable hashing, so a retry produces
  the same key and can be deduped.

  VersionedStore gives optimistic concurrency through compare and set, so a
  clash triggers a safe retry instead of a silent overwrite.

  The merge reducers let two agents update the same field by a rule (add, union,
  append) instead of last write wins.

The wider system also sidesteps the problem with event sourcing (see
event_log). The trust score is never a counter that gets overwritten. It is
folded from an append only log, where appends never conflict.
"""

from __future__ import annotations

import hashlib
import json
import threading
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


def canonical_json(value: Any) -> str:
    """Return deterministic JSON with sorted keys and no extra whitespace.

    Two payloads that mean the same thing serialize to the same string, so an
    idempotency key built from them is stable across retries and machines.
    """
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def idempotency_key(*parts: Any) -> str:
    """Build a stable key from parts such as run id, step, and content.

    A retried action carries the same key, so the system can dedupe it and never
    count a verdict twice or fire an action twice.
    """
    joined = "||".join(canonical_json(part) for part in parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


class VersionClash(Exception):
    """Raised when a compare and set sees a version it did not expect."""


class VersionedStore:
    """A thread safe key value store with optimistic concurrency.

    Every value carries a version. An update must state the version it read. If
    another writer moved the version in the meantime, the update fails and the
    caller retries with fresh data. A silent overwrite is not possible.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._data: Dict[str, Tuple[int, Any]] = {}

    def get(self, key: str) -> Tuple[int, Optional[Any]]:
        with self._lock:
            return self._data.get(key, (0, None))

    def compare_and_set(self, key: str, expected_version: int, new_value: Any) -> int:
        with self._lock:
            current_version, _ = self._data.get(key, (0, None))
            if current_version != expected_version:
                raise VersionClash(
                    "expected version "
                    + str(expected_version)
                    + " for key "
                    + repr(key)
                    + " but found "
                    + str(current_version)
                )
            new_version = current_version + 1
            self._data[key] = (new_version, new_value)
            return new_version

    def update_with_retry(
        self, key: str, transform: Callable[[Optional[Any]], Any], max_retries: int = 50
    ) -> Any:
        """Read, transform, and compare and set, retrying on a version clash.

        This is the safe replacement for read then write. The transform receives
        the current value (or None) and returns the new value. Under contention
        it retries against fresh state, so no update is ever lost.
        """
        for _ in range(max_retries):
            version, value = self.get(key)
            new_value = transform(value)
            try:
                self.compare_and_set(key, version, new_value)
                return new_value
            except VersionClash:
                continue
        raise VersionClash(
            "could not settle key " + repr(key) + " after " + str(max_retries) + " retries"
        )


def add_counter(current: Optional[int], delta: int) -> int:
    return (current or 0) + delta


def union_sets(current: Optional[Set[Any]], new_items: Set[Any]) -> Set[Any]:
    merged: Set[Any] = set(current or set())
    merged.update(new_items)
    return merged


def append_items(current: Optional[List[Any]], new_items: List[Any]) -> List[Any]:
    merged: List[Any] = list(current or [])
    merged.extend(new_items)
    return merged
