"""Coverage rejection tests; actual recorded replay is retained separately."""
from copy import deepcopy
import unittest

from field_thread_coverage import checked_schedule, join_native_window


def thread(qpc, opcode, pid=1, tid=10):
    return dict(kind='thread', qpc=qpc, cpu=0, opcode=opcode, fields=dict(pid=pid, tid=tid))


def switch(qpc, new, old, cpu=0):
    return dict(kind='cswitch', qpc=qpc, cpu=cpu, opcode=36, fields=dict(new_tid=new, old_tid=old))


def anchor(qpc, created=110, tid=10):
    return dict(status='OBSERVED', pid=1, tid=tid, process_created_filetime=50,
                thread_created_filetime=created, qpc_ticks=qpc, qpc_frequency=1000,
                perf_before_ns=qpc*1_000_000-1, perf_after_ns=qpc*1_000_000+1)


class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.rows = [thread(0, 1), switch(0, 10, 0), switch(4, 0, 10), switch(6, 10, 0),
                     switch(10, 0, 10), thread(11, 2)]
        self.header = dict(StartTime=100, EndTime=200, PerfFreq=1000, ReservedFlags=1,
                           EventsLost=0, BuffersLost=0, NumberOfProcessors=1)

    def join(self, rows=None, begin=None, end=None, header=None, **kwargs):
        return join_native_window(checked_schedule(self.rows if rows is None else rows, {10}, 1),
                                  begin or anchor(1), end or anchor(9), header or self.header,
                                  expected_pid=kwargs.get('pid', 1), expected_created_filetime=kwargs.get('created', 50))

    def test_new_thread_clipped_residency(self):
        r = self.join()
        self.assertEqual((r['wall_ticks'], r['residency_ticks'], r['outside_residency_ticks']), (8, 6, 2))
        self.assertEqual(r['origin_evidence'], 'NATIVE_AND_RECORDED_START')
        self.assertEqual(r['release_gate'], 'HOLD')
        self.assertFalse(r['promotion_allowed'])
        self.assertEqual(r['complete_trace_quality'], 'NOT_ESTABLISHED_BY_SELECTED_COVERAGE')

    def test_preexisting_terminal_end_and_rundown(self):
        for terminal in (2, 4):
            for start_rundown in (False, True):
                rows = self.rows[1:-1] + [thread(11, terminal)]
                if start_rundown:
                    rows.insert(0, thread(0, 3))
                with self.subTest(terminal=terminal, start_rundown=start_rundown):
                    r = self.join(rows, anchor(1, 60), anchor(9, 60))
                    self.assertEqual(r['origin_evidence'], 'NATIVE_PREEXISTING_WITH_TERMINAL_MAPPING')
                    self.assertEqual(r['terminal_evidence'], 'THREAD_END' if terminal == 2 else 'END_RUNDOWN')

    def test_new_thread_still_alive_at_trace_end(self):
        r = self.join(self.rows[:-1]+[thread(11, 4)])
        self.assertEqual(r['terminal_evidence'], 'END_RUNDOWN')

    def test_lifecycle_missing_reused_conflicting_pid(self):
        variants = [self.rows[:-1], self.rows+[thread(12, 1)], self.rows+[thread(12, 4)],
                    self.rows+[thread(12, 4, pid=2)], self.rows[1:],
                    self.rows[:-1]+[thread(8, 2)], self.rows+[thread(12, 3)]]
        for rows in variants:
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                self.join(sorted(rows, key=lambda r: r['qpc']))
        with self.assertRaisesRegex(ValueError, 'preexisting-thread-start-conflict'):
            self.join(begin=anchor(1, 60), end=anchor(9, 60))
        with self.assertRaisesRegex(ValueError, 'start-rundown-after-window-begin'):
            self.join(sorted(self.rows[1:]+[thread(2, 3)], key=lambda r: r['qpc']), anchor(1, 60), anchor(9, 60))

    def test_native_identity_unavailable_changed_or_wrong_external_generation(self):
        mutations = [('status', 'UNAVAILABLE'), ('tid', 11), ('thread_created_filetime', 111),
                     ('pid', 2), ('process_created_filetime', 51), ('qpc_frequency', 999),
                     ('qpc_ticks', True), ('thread_created_filetime', 49)]
        for key, value in mutations:
            end = anchor(9)
            end[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.join(end=end)
        for kwargs in ({'pid': 2}, {'created': 51}, {'created': True}):
            with self.assertRaises(ValueError):
                self.join(**kwargs)

    def test_native_clock_brackets_and_offset(self):
        for delta in (1000, -1000):
            end = anchor(9)
            end['perf_before_ns'] += delta
            end['perf_after_ns'] += delta
            with self.assertRaisesRegex(ValueError, 'native-clock-offset-disjoint'):
                self.join(end=end)
        for end in (anchor(1), anchor(0)):
            with self.assertRaises(ValueError):
                self.join(end=end)

    def test_recording_header_loss_clock_and_processors(self):
        for key, value in [('EventsLost', 1), ('BuffersLost', 1), ('EventsLost', False),
                           ('ReservedFlags', 2), ('ReservedFlags', True), ('PerfFreq', 0),
                           ('NumberOfProcessors', 2), ('StartTime', 201)]:
            header = dict(self.header, **{key: value})
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.join(header=header)

    def test_prefix_and_suffix_loss_with_zero_declared_loss(self):
        # Remaining switches still form a chain. Zero declared loss is insufficient.
        for rows in (self.rows[:1]+self.rows[2:], self.rows[:-2]+self.rows[-1:]):
            with self.assertRaisesRegex(ValueError, 'window-outside-processor-coverage'):
                self.join(rows)

    def test_switch_gap_reversal_same_time_and_overlap(self):
        variants = [self.rows[:2]+self.rows[3:], [self.rows[0], self.rows[2], self.rows[1]]+self.rows[3:],
                    self.rows[:2]+[switch(0, 0, 10)]+self.rows[2:]]
        for rows in variants:
            with self.assertRaises(ValueError):
                checked_schedule(rows, {10}, 1)
        overlap = sorted(self.rows+[switch(0, 0, 0, 1), switch(2, 10, 0, 1),
                                    switch(8, 0, 10, 1), switch(10, 0, 0, 1)], key=lambda r: r['qpc'])
        with self.assertRaisesRegex(ValueError, 'thread-running-on-two-processors'):
            checked_schedule(overlap, {10}, 2)
        with self.assertRaisesRegex(ValueError, 'processor-coverage'):
            checked_schedule(self.rows, {10}, 2)

    def test_boundary_not_running_or_exact_switch_time(self):
        for begin in (anchor(4), anchor(5), anchor(6)):
            with self.assertRaisesRegex(ValueError, 'begin-not-in-one-residency'):
                self.join(begin=begin)
        with self.assertRaisesRegex(ValueError, 'end-not-in-one-residency'):
            self.join(end=anchor(4))

    def test_event_field_validation_and_budgets(self):
        for key, value in [('qpc', True), ('cpu', -1), ('cpu', 1), ('kind', 'unknown'), ('opcode', True)]:
            rows = deepcopy(self.rows)
            rows[0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                checked_schedule(rows, {10}, 1)
        for targets, cpus in [(set(), 1), ({True}, 1), ({10}, 129), ({10}, True)]:
            with self.assertRaises(ValueError):
                checked_schedule(self.rows, targets, cpus)


if __name__ == '__main__':
    unittest.main()
