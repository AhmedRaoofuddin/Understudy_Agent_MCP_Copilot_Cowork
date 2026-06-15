"""The playbook: a team learned, editable procedure for a task class.

A playbook is the structured way a team does a kind of task. It is learned by
watching demonstrations and confirmed by a human. It is intentionally editable,
not a hidden guess.

The store reuses the versioned store from the core concurrency module, so two
agents updating the same playbook at once cannot lose each other changes. The
version increments on every update, which is also how a reviewer can see what
changed since the last release.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from core.concurrency import VersionedStore


@dataclass
class Playbook:
    domain: str
    verb: str
    steps: List[str] = field(default_factory=list)
    parameters: List[str] = field(default_factory=list)
    version: int = 0
    confirmed: bool = False


class PlaybookStore:
    def __init__(self) -> None:
        self._store = VersionedStore()

    @staticmethod
    def _key(domain: str, verb: str) -> str:
        return domain.strip().upper() + ":" + verb.strip().upper()

    def get(self, domain: str, verb: str) -> Optional[Playbook]:
        _, value = self._store.get(self._key(domain, verb))
        return value

    def upsert(self, playbook: Playbook) -> Playbook:
        key = self._key(playbook.domain, playbook.verb)

        def transform(current: Optional[Playbook]) -> Playbook:
            base_version = current.version if current is not None else 0
            playbook.version = base_version + 1
            return playbook

        return self._store.update_with_retry(key, transform)
