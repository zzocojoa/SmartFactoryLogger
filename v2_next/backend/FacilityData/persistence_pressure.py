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

    @property
    def has_pending(self) -> bool:
        return bool(self.pending_count or self.pending_bytes or self.spool_bytes or self.pending_recovery)


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
        active = [sample for sample in samples if sample.enabled or sample.has_pending]
        availability = ("blocked" if any(sample.availability == "blocked" for sample in active)
                        else "unknown" if any(sample.availability != "available" for sample in active)
                        else "available")
        reasons = set() if availability == "available" else {"storage_" + availability}
        occupancy = max((max(sample.pending_count / sample.count_limit, sample.pending_bytes / sample.byte_limit,
                             sample.spool_bytes / sample.spool_limit) for sample in active), default=0.0)
        overdue = max((max(0.0, now_monotonic - sample.stage_due_monotonic) for sample in active
                       if sample.has_pending and sample.stage_due_monotonic is not None), default=0.0)
        oldest_age = max((max(0.0, now_monotonic - sample.oldest_pending_monotonic) for sample in active
                          if sample.has_pending and sample.oldest_pending_monotonic is not None), default=None)
        if occupancy >= 1.0:
            reasons.add("budget_exhausted")
        if any(sample.manual_recovery_required for sample in active):
            reasons.add("manual_recovery")
        if any(not sample.writer_alive for sample in active):
            reasons.add("writer_stopped")
        blocked = bool(reasons)
        if occupancy >= 0.8:
            reasons.add("occupancy_high")
        if overdue >= 2.0:
            reasons.add("stage_overdue")
        state = "PERSISTENCE_BLOCKED" if blocked else "PRESSURED" if reasons else "NORMAL"
        return StoragePressureDecision(state, availability, occupancy, overdue, oldest_age,
                                       sum(sample.pending_recovery for sample in active), 0, tuple(sorted(reasons)))
