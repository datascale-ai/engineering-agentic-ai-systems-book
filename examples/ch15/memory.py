"""Scoped memory and verifiable deletion from live in-memory layers.

Authenticated caller identities must be bound by the application. Backups
are modeled explicitly and remain retained until restore/retention handling.
"""

from copy import deepcopy
from dataclasses import asdict, dataclass


@dataclass
class Memory:
    memory_id: str
    tenant_id: str
    owner_id: str
    key: str
    value: str
    kind: str
    scope: str
    session_id: str | None
    valid_from: int
    valid_until: int
    revision: int
    source_ref: str


class MemoryStore:
    def __init__(self):
        self.primary = {}
        self.index = {}
        self.cache = {}
        self.backup = {}
        self.tombstones = set()
        self.epoch = 0

    def put(self, record, tenant_id, owner_id):
        if record.tenant_id != tenant_id or record.owner_id != owner_id:
            raise PermissionError("owner_scope")
        if record.kind not in {"episodic", "semantic", "procedural"}:
            raise ValueError("kind")
        if record.scope not in {"session", "user"} or not record.source_ref:
            raise ValueError("scope_or_source")
        if record.scope == "session" and not record.session_id:
            raise ValueError("session_required")
        if (
            record.valid_until <= record.valid_from
            or record.memory_id in self.tombstones
        ):
            raise ValueError("expired_interval_or_deleted_id")
        old = self.primary.get(record.memory_id)
        if old and (
            old.tenant_id != tenant_id
            or old.owner_id != owner_id
            or record.revision <= old.revision
        ):
            raise ValueError("revision_or_owner")
        self.primary[record.memory_id] = deepcopy(record)
        self.index[record.memory_id] = (record.tenant_id, record.owner_id, record.key)
        self.epoch += 1
        self.cache.clear()

    def recall(self, tenant_id, owner_id, key, session_id, now):
        cache_key = (tenant_id, owner_id, key, session_id, now, self.epoch)
        if cache_key in self.cache:
            return deepcopy(self.cache[cache_key])
        records = [
            m
            for mid, m in self.primary.items()
            if mid in self.index
            and mid not in self.tombstones
            and m.tenant_id == tenant_id
            and m.owner_id == owner_id
            and m.key == key
            and m.valid_from <= now < m.valid_until
            and (m.scope == "user" or m.session_id == session_id)
        ]
        result = max(
            records,
            key=lambda m: (m.scope == "session", m.revision, m.valid_from, m.memory_id),
            default=None,
        )
        self.cache[cache_key] = deepcopy(result)
        return deepcopy(result)

    def delete(self, memory_id, tenant_id, owner_id):
        record = self.primary.get(memory_id) or self.backup.get(memory_id)
        if record and (record.tenant_id != tenant_id or record.owner_id != owner_id):
            raise PermissionError("owner_scope")
        self.tombstones.add(memory_id)
        self.primary.pop(memory_id, None)
        self.index.pop(memory_id, None)
        self.epoch += 1
        self.cache.clear()
        return {
            "memory_id": memory_id,
            "primary": "absent",
            "index": "absent",
            "cache": "invalidated",
            "backup": "retained_until_expiry" if memory_id in self.backup else "absent",
            "restore_filter": "tombstone_required",
        }

    def snapshot(self):
        self.backup = deepcopy(self.primary)

    def restore(self):
        self.primary = {
            k: deepcopy(v) for k, v in self.backup.items() if k not in self.tombstones
        }
        self.index = {
            k: (v.tenant_id, v.owner_id, v.key) for k, v in self.primary.items()
        }
        self.epoch += 1
        self.cache.clear()
