"""Append only, hash chained event log: the single source of truth.

We never store a mutable current trust score that agents overwrite. We store
immutable events. Trust scores are derived by folding these events (see
projections). Because appends never conflict, concurrent writers cannot lose
each other updates, and an idempotency key makes a retried append a no op.

Each event is chained to the previous one with a hash, so the log is tamper
evident. If a past event is altered, verify_chain reports it.

For the first phase this is an in memory log so the proof harness runs anywhere
with no database. The same interface is later backed by Postgres in production.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

from core.concurrency import canonical_json

GENESIS_HASH = "0" * 64

KIND_VERDICT = "VERDICT"
KIND_OUTCOME = "OUTCOME"

VERDICT_APPROVE = "APPROVE"
VERDICT_EDIT = "EDIT"
VERDICT_REJECT = "REJECT"

OUTCOME_CONFIRMED = "CONFIRMED"
OUTCOME_REVERTED = "REVERTED"
OUTCOME_PENDING = "PENDING"


@dataclass(frozen=True)
class Event:
    event_id: str
    seq: int
    bucket_key: str
    kind: str
    task_id: str
    data: Dict[str, Any]
    timestamp: float
    prev_hash: str
    hash: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def compute_event_hash(
    event_id: str,
    seq: int,
    bucket_key: str,
    kind: str,
    task_id: str,
    data: Dict[str, Any],
    timestamp: float,
    prev_hash: str,
) -> str:
    body = canonical_json(
        {
            "event_id": event_id,
            "seq": seq,
            "bucket_key": bucket_key,
            "kind": kind,
            "task_id": task_id,
            "data": data,
            "timestamp": timestamp,
            "prev_hash": prev_hash,
        }
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


class EventLog:
    """A thread safe append only log with idempotent appends and a hash chain.

    There is deliberately no update or delete method. The only mutation is
    append, and append is atomic under a lock, so concurrent writers serialize
    cleanly and the chain stays consistent.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._events: List[Event] = []
        self._seen_event_ids: Dict[str, int] = {}

    def append(
        self,
        event_id: str,
        bucket_key: str,
        kind: str,
        task_id: str,
        data: Dict[str, Any],
        timestamp: Optional[float] = None,
    ) -> bool:
        """Append an event. Return True if appended, False if it is a duplicate.

        A duplicate event id (a retry) is ignored, so retries never double count.
        That is the idempotency guarantee.
        """
        with self._lock:
            if event_id in self._seen_event_ids:
                return False
            seq = len(self._events)
            prev_hash = self._events[-1].hash if self._events else GENESIS_HASH
            stamp = timestamp if timestamp is not None else time.time()
            event_hash = compute_event_hash(
                event_id, seq, bucket_key, kind, task_id, data, stamp, prev_hash
            )
            event = Event(
                event_id, seq, bucket_key, kind, task_id, data, stamp, prev_hash, event_hash
            )
            self._events.append(event)
            self._seen_event_ids[event_id] = seq
            self._persist(event)
            return True

    def _persist(self, event: Event) -> None:
        """Hook for durable storage. The in memory log does nothing here."""

    def events_for_bucket(self, bucket_key: str) -> List[Event]:
        with self._lock:
            return [event for event in self._events if event.bucket_key == bucket_key]

    def all_events(self) -> List[Event]:
        with self._lock:
            return list(self._events)

    def count(self) -> int:
        with self._lock:
            return len(self._events)

    def verify_chain(self) -> bool:
        """Recompute the hash chain and confirm nothing was tampered with."""
        with self._lock:
            prev_hash = GENESIS_HASH
            for event in self._events:
                expected = compute_event_hash(
                    event.event_id,
                    event.seq,
                    event.bucket_key,
                    event.kind,
                    event.task_id,
                    event.data,
                    event.timestamp,
                    prev_hash,
                )
                if expected != event.hash or event.prev_hash != prev_hash:
                    return False
                prev_hash = event.hash
            return True


class FileEventLog(EventLog):
    """An event log that also appends every event to a JSON lines file and loads
    the existing history on startup.

    A long running server keeps its memory across restarts this way. The file is
    the durable form of the same append only log, so the hash chain and the
    idempotency guarantees still hold.
    """

    def __init__(self, path: str) -> None:
        super().__init__()
        self._path = path
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self._path):
            return
        with open(self._path, "r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped:
                    continue
                record = json.loads(stripped)
                event = Event(**record)
                self._events.append(event)
                self._seen_event_ids[event.event_id] = event.seq

    def _persist(self, event: Event) -> None:
        with open(self._path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(event.to_dict()) + "\n")
