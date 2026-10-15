"""Join native thread windows to independently checked, same-recording events.

Pure analysis only: the caller must pin the ETL, selected export, independent
crosscheck, header and native request evidence. No WPR/app control or field gate.
Rundown describes a running thread; its timestamp is not thread creation/exit.
CSwitch residency includes unmeasured DPC/ISR and is not exact thread CPU time.
"""
from collections import defaultdict
from dataclasses import dataclass

from field_health_timing import ANCHOR_KEYS, integer, require


@dataclass(frozen=True)
class Schedule:
    spans: dict
    bounds: dict
    lifecycle: dict
    ready: dict
    targets: frozenset
    event_count: int


def checked_schedule(rows, target_tids, cpu_count):
    """Fail closed on gaps, processor ambiguity, reuse evidence and bad order.

    This checks internal consistency, not arbitrary loss-free recording. Even
    EventsLost=0 does not establish that a circular trace retained its prefix.
    """
    require(integer(cpu_count, upper=129), 'processor-count')
    targets = frozenset(target_tids)
    require(0 < len(targets) <= 16 and all(integer(t, upper=2**32) for t in targets), 'target-tids')
    previous, last, bounds = None, {}, {}
    spans, lifecycle, ready = (defaultdict(list) for _ in range(3))
    count = 0
    for row in rows:
        count += 1
        require(count <= 1_000_000, 'event-count-budget')
        qpc, cpu, kind, fields = (row[k] for k in ('qpc', 'cpu', 'kind', 'fields'))
        require(integer(qpc, zero=True), 'event-qpc')
        require(previous is None or qpc >= previous, 'event-order')
        previous = qpc
        require(integer(cpu, zero=True, upper=cpu_count), 'processor-id')
        require(kind in ('thread', 'cswitch', 'ready') and type(fields) is dict, 'selected-event-kind')
        opcode = row['opcode']
        require(type(opcode) is int, 'event-opcode')
        if kind == 'thread':
            require(opcode in (1, 2, 3, 4), 'thread-opcode')
            require(all(integer(fields[k], zero=True, upper=2**32) for k in ('pid', 'tid')), 'thread-ids')
            if fields['tid'] in targets:
                lifecycle[fields['tid']].append((qpc, opcode, fields['pid']))
        elif kind == 'ready':
            require(opcode == 50 and integer(fields['target_tid'], zero=True, upper=2**32), 'ready-fields')
            if fields['target_tid'] in targets:
                ready[fields['target_tid']].append(qpc)
        else:
            require(opcode == 36 and all(integer(fields[k], zero=True, upper=2**32)
                                        for k in ('old_tid', 'new_tid')), 'switch-fields')
            prior = last.get(cpu)
            if prior is not None:
                require(prior[0] < qpc, 'ambiguous-switch-time')
                require(prior[1] == fields['old_tid'], 'switch-chain-gap')
                if prior[1] in targets:
                    spans[prior[1]].append((prior[0], qpc, cpu))
            else:
                bounds[cpu] = [qpc, qpc]
            bounds[cpu][1] = qpc
            last[cpu] = (qpc, fields['new_tid'])
    require(set(bounds) == set(range(cpu_count)), 'processor-coverage')
    for tid in targets:
        spans[tid].sort()
        require(all(left[1] <= right[0] for left, right in zip(spans[tid], spans[tid][1:])),
                'thread-running-on-two-processors')
    return Schedule(dict(spans), bounds, dict(lifecycle), dict(ready), targets, count)


def _native_window(begin, end, header, expected_pid, expected_created_filetime):
    require(integer(expected_pid, upper=2**32) and integer(expected_created_filetime, upper=2**64),
            'external-process-generation')
    for key in ('PerfFreq', 'StartTime', 'EndTime', 'NumberOfProcessors'):
        require(integer(header[key], upper=2**64), 'header-values')
    require(header['StartTime'] < header['EndTime'], 'header-time-order')
    require(type(header['ReservedFlags']) is int and header['ReservedFlags'] == 1, 'header-not-qpc')
    require(all(type(header[k]) is int and header[k] == 0 for k in ('EventsLost', 'BuffersLost')),
            'declared-trace-loss')
    for anchor in (begin, end):
        require(type(anchor) is dict and set(anchor) == ANCHOR_KEYS and anchor['status'] == 'OBSERVED',
                'native-anchor-unavailable')
        require(all(integer(anchor[k], upper=2**32) for k in ('pid', 'tid'))
                and all(integer(anchor[k], upper=2**64) for k in (
                    'process_created_filetime', 'thread_created_filetime'))
                and all(integer(anchor[k], zero=True) for k in (
                    'qpc_ticks', 'perf_before_ns', 'perf_after_ns'))
                and integer(anchor['qpc_frequency']), 'native-anchor-values')
        require(anchor['process_created_filetime'] <= anchor['thread_created_filetime'] <= header['EndTime'],
                'native-creation-order')
        require(anchor['pid'] == expected_pid and anchor['process_created_filetime'] == expected_created_filetime,
                'native-process-generation')
        require(anchor['perf_before_ns'] <= anchor['perf_after_ns'], 'native-bracket-order')
        require(anchor['qpc_frequency'] == header['PerfFreq'], 'native-frequency-mismatch')
    require(begin['tid'] == end['tid'] and begin['thread_created_filetime'] == end['thread_created_filetime'],
            'native-thread-generation')
    require(begin['qpc_ticks'] < end['qpc_ticks'] and begin['perf_after_ns'] <= end['perf_before_ns'],
            'native-window-order')
    frequency = header['PerfFreq']
    offsets = [(a['perf_before_ns'] - (a['qpc_ticks'] * 1_000_000_000 + frequency - 1) // frequency,
                a['perf_after_ns'] - a['qpc_ticks'] * 1_000_000_000 // frequency) for a in (begin, end)]
    require(max(a for a, _ in offsets) <= min(b for _, b in offsets), 'native-clock-offset-disjoint')


def join_native_window(schedule, begin, end, header, *, expected_pid, expected_created_filetime):
    """Return selected-event coverage, retaining field/whole-trace limitations.

    Conservative single-generation rule across the complete selected export:
    require one End OR one DCEnd after the window; reject PID conflicts, repeated
    lifecycle records, and unsupported start/rundown combinations. A preexisting
    thread can lack Start/DCStart when native generation plus terminal mapping
    and the full processor scheduling window are present. No invented birth QPC.
    """
    _native_window(begin, end, header, expected_pid, expected_created_filetime)
    tid, first, last = begin['tid'], begin['qpc_ticks'], end['qpc_ticks']
    require(tid in schedule.targets, 'thread-not-selected')
    require(len(schedule.bounds) == header['NumberOfProcessors'], 'header-processor-count')
    records = schedule.lifecycle.get(tid, [])
    require(records and {pid for _, _, pid in records} == {expected_pid}, 'thread-pid-ambiguous')
    by_opcode = {op: [q for q, opcode, _ in records if opcode == op] for op in (1, 2, 3, 4)}
    require(all(len(q) <= 1 for q in by_opcode.values()), 'thread-lifecycle-duplicate-or-reused')
    terminals = [(q, op) for q, op, _ in records if op in (2, 4)]
    require(len(terminals) == 1 and terminals[0][0] > last, 'thread-terminal-mapping-missing-or-conflicting')
    preexisting = begin['thread_created_filetime'] < header['StartTime']
    if preexisting:
        require(not by_opcode[1], 'preexisting-thread-start-conflict')
        require(not by_opcode[3] or by_opcode[3][0] < first, 'start-rundown-after-window-begin')
        origin = 'NATIVE_PREEXISTING_WITH_TERMINAL_MAPPING'
    else:
        require(len(by_opcode[1]) == 1 and by_opcode[1][0] < first and not by_opcode[3],
                'new-thread-start-missing-or-conflicting')
        origin = 'NATIVE_AND_RECORDED_START'
    require(all(a < first < last < b for a, b in schedule.bounds.values()), 'window-outside-processor-coverage')
    spans = schedule.spans.get(tid, [])
    # A native user-mode boundary lies strictly inside a residency interval.
    # Equality is ambiguous at finite QPC resolution and must not be guessed.
    require(sum(a < first < b for a, b, _ in spans) == 1, 'begin-not-in-one-residency')
    require(sum(a < last < b for a, b, _ in spans) == 1, 'end-not-in-one-residency')
    clipped = [(max(a, first), min(b, last), cpu) for a, b, cpu in spans if a < last and b > first]
    ticks = sum(b - a for a, b, _ in clipped)
    require(0 < ticks <= last - first, 'invalid-residency-sum')
    frequency = header['PerfFreq']
    return dict(status='NATIVE_WINDOW_JOINED_TO_SELECTED_CSWITCH', identity={k: begin[k] for k in (
                    'pid', 'tid', 'process_created_filetime', 'thread_created_filetime')},
                origin_evidence=origin, lifecycle_records=[dict(qpc=q, opcode=op, pid=pid) for q, op, pid in records],
                terminal_evidence='THREAD_END' if terminals[0][1] == 2 else 'END_RUNDOWN',
                first_qpc=first, last_qpc=last, frequency=frequency, wall_ticks=last-first,
                residency_ticks=ticks, outside_residency_ticks=last-first-ticks,
                wall_ms=(last-first)*1000/frequency, cswitch_residency_ms=ticks*1000/frequency,
                outside_residency_ms=(last-first-ticks)*1000/frequency,
                residency_segments=[dict(first=a, last=b, cpu=cpu) for a, b, cpu in clipped],
                ready_events_in_window=sum(first <= q < last for q in schedule.ready.get(tid, [])),
                complete_trace_quality='NOT_ESTABLISHED_BY_SELECTED_COVERAGE', exact_cpu_time='NOT_EVALUATED',
                latency_cause='UNDETERMINED', field_gate='NOT_EVALUATED', release_gate='HOLD', promotion_allowed=False)
