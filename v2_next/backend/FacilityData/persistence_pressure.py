"""Memory-only storage pressure decisions; owner I/O is deliberately separate."""
from dataclasses import dataclass, field, replace
import threading
import time
from typing import Callable, Iterable

from backend.FacilityData.freshness import clock_domain_id, finite_number


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
    max_stage_overdue_seconds: float | None
    oldest_pending_age_seconds: float | None
    pending_recovery: int
    normal_confirmations: int
    reasons: tuple[str, ...]
    sampling_failure_count: int = 0


class StoragePressureController:
    def __init__(self) -> None:
        self._last_checked: float | None = None
        self._last_decision: StoragePressureDecision | None = None
        self._normal_confirmations = 0

    def mark_unavailable(self, *, now_monotonic: float, reason: str) -> StoragePressureDecision:
        self._last_checked = now_monotonic
        self._normal_confirmations = 0
        self._last_decision = StoragePressureDecision("PERSISTENCE_BLOCKED", "unknown", 0.0, None, None,
                                                      0, 0, (reason,))
        return self._last_decision

    def evaluate(self, samples: Iterable[StoragePressureSample], *, now_monotonic: float) -> StoragePressureDecision:
        if self._last_checked is not None and now_monotonic - self._last_checked < 1.0:
            assert self._last_decision is not None
            return self._last_decision
        active = [sample for sample in samples
                  if sample.enabled or sample.has_pending or sample.manual_recovery_required]
        availability = ("blocked" if any(sample.availability == "blocked" for sample in active)
                        else "unknown" if any(sample.availability != "available" for sample in active)
                        else "available")
        reasons = set() if availability == "available" else {"storage_" + availability}
        occupancy = max((max(sample.pending_count / sample.count_limit, sample.pending_bytes / sample.byte_limit,
                             sample.spool_bytes / sample.spool_limit) for sample in active), default=0.0)
        pending_times = []
        for sample in active:
            if not sample.has_pending:
                continue
            oldest = finite_number(sample.oldest_pending_monotonic)
            due = finite_number(sample.stage_due_monotonic)
            if (sample.clock_domain != clock_domain_id() or oldest is None or due is None
                    or oldest < 0 or oldest > now_monotonic or due < oldest):
                reasons.add("pending_clock_unavailable")
            else:
                pending_times.append((oldest, due))
        overdue = (None if "pending_clock_unavailable" in reasons
                   else max((max(0.0, now_monotonic - due) for _, due in pending_times), default=0.0))
        oldest_age = (None if "pending_clock_unavailable" in reasons
                      else max((now_monotonic - oldest for oldest, _ in pending_times), default=None))
        if occupancy >= 1.0:
            reasons.add("budget_exhausted")
        if any(sample.manual_recovery_required for sample in active):
            reasons.add("manual_recovery")
        if any(not sample.writer_alive for sample in active):
            reasons.add("writer_stopped")
        blocked = bool(reasons)
        if occupancy >= 0.8:
            reasons.add("occupancy_high")
        if overdue is not None and overdue >= 2.0:
            reasons.add("stage_overdue")
        pending_recovery = sum(sample.pending_recovery for sample in active)
        if blocked:
            state = "PERSISTENCE_BLOCKED"
            self._normal_confirmations = 0
        elif reasons:
            state = "PRESSURED"
            self._normal_confirmations = 0
        elif self._last_decision is not None and self._last_decision.state != "NORMAL":
            recovering = occupancy <= 0.5 and overdue is not None and overdue < 1.0 and pending_recovery == 0
            self._normal_confirmations = self._normal_confirmations + 1 if recovering else 0
            state = "NORMAL" if self._normal_confirmations >= 3 else "PRESSURED"
            if state == "PRESSURED":
                reasons.add("normal_recovery_confirmation")
        else:
            state = "NORMAL"
            self._normal_confirmations = 0
        self._last_checked = now_monotonic
        self._last_decision = StoragePressureDecision(state, availability, occupancy, overdue, oldest_age,
                                                      pending_recovery, self._normal_confirmations, tuple(sorted(reasons)))
        return self._last_decision


class StoragePressureMonitor:
    # Two missed one-second controller intervals invalidate published health.
    _STALE_AFTER_SECONDS = 2.0

    def __init__(self, sample_provider: Callable[[], Iterable[StoragePressureSample]]) -> None:
        self.sample_provider = sample_provider
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._controller = StoragePressureController()
        self._sampling_failure_count = 0
        self._decision = self._unavailable_decision("not_started")
        self._decision_at: float | None = None

    def _unavailable_decision(self, reason: str) -> StoragePressureDecision:
        return StoragePressureDecision("PERSISTENCE_BLOCKED", "unknown", 0.0, None, None,
                                       0, 0, (reason,), self._sampling_failure_count)

    def start(self) -> bool:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return False
            self._stop.clear()
            self._controller = StoragePressureController()
            self._decision = self._unavailable_decision("starting")
            self._decision_at = None
            self._thread = threading.Thread(target=self._run, name="storage-pressure-controller", daemon=True)
            self._thread.start()
            return True

    def _run(self) -> None:
        try:
            while not self._stop.is_set():
                started = time.monotonic()
                try:
                    samples = tuple(self.sample_provider())
                    sampled_at = time.monotonic()
                    if sampled_at - started >= self._STALE_AFTER_SECONDS:
                        with self._lock:
                            self._sampling_failure_count += 1
                        decision = self._controller.mark_unavailable(now_monotonic=sampled_at, reason="sampling_stale")
                    else:
                        decision = self._controller.evaluate(samples, now_monotonic=sampled_at)
                except Exception:
                    with self._lock:
                        self._sampling_failure_count += 1
                    decision = self._controller.mark_unavailable(now_monotonic=started, reason="sampling_failed")
                with self._lock:
                    self._decision_at = started
                    self._decision = (self._unavailable_decision("monitor_stopping") if self._stop.is_set()
                                      else replace(decision, sampling_failure_count=self._sampling_failure_count))
                self._stop.wait(max(0.0, 1.0 - (time.monotonic() - started)))
        finally:
            with self._lock:
                if self._thread is threading.current_thread():
                    self._decision = self._unavailable_decision("monitor_stopped")

    def snapshot(self) -> StoragePressureDecision:
        with self._lock:
            if (not self._stop.is_set() and self._decision_at is not None
                    and time.monotonic() - self._decision_at >= self._STALE_AFTER_SECONDS):
                return self._unavailable_decision("sampling_stale")
            return self._decision

    def stop(self, timeout: float = 2.0) -> bool:
        with self._lock:
            thread = self._thread
            self._stop.set()
            self._decision = self._unavailable_decision("monitor_stopping" if thread else "monitor_stopped")
        if thread is None:
            return True
        thread.join(timeout=max(0.0, timeout))
        stopped = not thread.is_alive()
        if stopped:
            with self._lock:
                if self._thread is thread:
                    self._thread = None
        return stopped
