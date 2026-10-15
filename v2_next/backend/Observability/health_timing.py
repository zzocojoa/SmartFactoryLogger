"""Opt-in loopback health checkpoints; wall time, not CPU or network time."""
from dataclasses import dataclass, field
import ipaddress
import json
import os
import re
import threading
import time

from starlette.requests import Request
from backend.Observability.health_clock import capture_health_clock


PROBE_HEADER = "X-SFL-Health-Probe"
TIMING_HEADER = "X-SFL-Health-Timing"


@dataclass
class HealthTiming:
    probe_id: str
    pid: int = field(default_factory=os.getpid)
    loop_tid: int = field(default_factory=threading.get_native_id)
    worker_tid: int = 0
    checkpoints: dict[str, int] = field(default_factory=dict)
    native: dict[str, dict] = field(default_factory=dict)

    def mark(self, name: str) -> None:
        self.checkpoints[name] = time.perf_counter_ns()

    def header(self) -> str:
        # All names are fixed by the health route; only a validated hex ID is echoed.
        return json.dumps({
            "v": 2, "probe_id": self.probe_id, "pid": self.pid,
            "loop_tid": self.loop_tid, "worker_tid": self.worker_tid,
            "clock": "perf_counter_ns", "checkpoints": self.checkpoints,
            "native": self.native,
        }, separators=(",", ":"), ensure_ascii=True)


def start_health_timing(request: Request) -> HealthTiming | None:
    values = request.headers.getlist(PROBE_HEADER)
    if len(values) != 1 or re.fullmatch(r"[0-9a-f]{32}", values[0]) is None:
        return None
    # This is a diagnostic filter, not a substitute for the app's access controls.
    if request.client is None or "origin" in request.headers or "referer" in request.headers:
        return None
    try:
        if not ipaddress.ip_address(request.client.host).is_loopback:
            return None
    except ValueError:
        return None
    timing = HealthTiming(values[0])
    timing.mark("route_enter")
    timing.native["loop_begin"] = capture_health_clock()
    return timing
