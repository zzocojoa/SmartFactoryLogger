"""Memory-only storage pressure decisions; owner I/O is deliberately separate."""
from dataclasses import dataclass, field
from typing import Iterable

from backend.FacilityData.freshness import clock_domain_id


@dataclass(frozen=True)
class StoragePressureSample:
    sink_id: str
    config_generation: int
    destination_key: str
    enabled: bool
    availability: str
    pending_count: int = 0
    pending_bytes: int = 0
    count_limit: int = 1
    byte_limit: int = 1
    spool_bytes: int = 0
    spool_limit: int = 1
    pending_recovery: int = 0
    oldest_pending_monotonic: float | None = None
    stage_due_monotonic: float | None = None
    clock_domain: str = field(default_factory=clock_domain_id)
    writer_alive: bool = True
    manual_recovery_required: bool = False


@dataclass(frozen=True)
class StoragePressureDecision:
    state: str
    current_storage_availability: str
    max_occupancy_ratio: float
    max_stage_overdue_seconds: float
    oldest_pending_age_seconds: float | None
    pending_recovery: int
    normal_confirmations: int
    reasons: tuple[str, ...]


class StoragePressureController:
    def evaluate(self, samples: Iterable[StoragePressureSample], *, now_monotonic: float) -> StoragePressureDecision:
        active = [sample for sample in samples if sample.enabled or sample.pending_count or sample.pending_bytes
                  or sample.spool_bytes or sample.pending_recovery]
        availability = ("blocked" if any(sample.availability == "blocked" for sample in active)
                        else "unknown" if any(sample.availability != "available" for sample in active)
                        else "available")
        reasons = () if availability == "available" else ("storage_" + availability,)
        state = "NORMAL" if not reasons else "PERSISTENCE_BLOCKED"
        return StoragePressureDecision(state, availability, 0.0, 0.0, None, 0, 0, reasons)
