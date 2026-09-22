"""C3 production request/publisher/fact/CSV tests with independent clocks and mock HTTP."""
import asyncio
import csv
import tempfile
import unittest
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import httpx

from backend.FacilityData.drivers import spot_api
from backend.FacilityData.drivers.real_plc import RealPLCDriver
from backend.FacilityData.freshness import clock_domain_id
from backend.FacilityData.repository import CSVLoggerService
from backend.FacilityData import repository
from backend.FacilityData.schemas import FactoryData
from backend.FacilityData.spot_observation import classify_spot_raw_response
from backend.FacilityData.spot_observation_fact import SpotObservationFactWriter
from backend.FacilityData import spot_observation_fact as fact_module
from scripts import validate_csv_v2_shadow as validator
from backend.FacilityData.spot_observation_queue import SpotObservationQueue
from backend.tests.test_temperature_followup_polling import IndependentClock


class PollDurationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.tmp = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.clock = IndependentClock()
        self.stack.enter_context(patch.object(repository, 'time', self.clock))
        self.path = self.tmp / 'spot_observation_fact.csv'
        self.owner = SpotObservationQueue(lambda: SpotObservationFactWriter(self.path))
        self.addCleanup(self.owner.close, 2)
        for name, value in {'SPOT_URL':'http://spot.test/output?p=temperature',
                            'SPOT_OBSERVATION_FACT_ENABLED':True, 'LOG_PATH':str(self.tmp),
                            'CSV_V2_ENABLED':True, 'CSV_V2_TEMPERATURE_HARDENING_ENABLED':True,
                            'CSV_V2_OPERATIONAL_FIELDS_ENABLED':True}.items():
            self.stack.enter_context(patch.object(spot_api.config, name, value))
        for name, value in {'time':self.clock, '_spot_poll_seq':0, '_spot_observation_seq':0,
            '_spot_temperature_snapshot':None, '_spot_last_valid_value_at':None,
            '_spot_last_valid_value_monotonic':None, '_spot_temperature_cache_suppressed_until_valid':False,
            '_temperature_cache':{}, '_spot_observation_queue':self.owner,
            '_spot_diagnostics_snapshot':None,
            '_spot_observation_queue_path':self.path.resolve()}.items():
            self.stack.enter_context(patch.object(spot_api, name, value))

    def csv_row(self):
        metadata = spot_api._build_spot_temperature_snapshot_diagnostics(self.clock.wall)
        fields = RealPLCDriver._spot_metadata_to_factory_fields(None, metadata)
        data = FactoryData(Time='', Spot=metadata.get('spot_temperature_effective_c'), **fields)
        logger = CSVLoggerService()
        now = datetime.fromtimestamp(self.clock.wall, timezone.utc)
        # Writer clock is independent; current observation uses its preserved UTC.
        values = logger._build_v2_row(data, now, now, 1, logger._build_row(data, now))
        return dict(zip(logger._get_active_v2_contract().columns, values))

    async def test_all_completed_request_paths_wall_jumps_fact_csv_and_utc(self):
        expected = []
        for kind in ['valid', 'under', 'over', 'timeout', 'connection', 'http', 'config']:
            for jump in [0, -60, 60, -60, 60]:
                with self.subTest(kind=kind, jump=jump):
                    start = self.clock.wall
                    async def transport(request):
                        self.clock.advance(.2)
                        self.clock.wall += jump
                        if kind == 'timeout':
                            raise httpx.ReadTimeout('synthetic timeout', request=request)
                        if kind == 'connection':
                            raise httpx.ConnectError('synthetic connection', request=request)
                        return httpx.Response(503 if kind=='http' else 200,
                            text={'under':'6553.4','over':'6553.5'}.get(kind,'500'), request=request)
                    # Config resolution is part of the original poll boundary.
                    class MissingConfig:
                        def __bool__(inner):
                            self.clock.advance(.2)
                            self.clock.wall += jump
                            return False
                    with patch.object(spot_api.config, 'SPOT_URL', MissingConfig() if kind=='config' else 'http://spot.test/output?p=temperature'):
                        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
                            try:
                                await spot_api._refresh_spot_temperature(client)
                            except (spot_api.SpotTemperatureConfigError, spot_api.SpotTemperatureFetchError):
                                self.assertIn(kind, ['under','over','timeout','connection','http','config'])
                    snapshot = spot_api.get_spot_temperature_poll_snapshot()
                    self.assertAlmostEqual(snapshot['spot_poll_duration_ms'], 200, places=5)
                    self.assertEqual(snapshot['spot_poll_duration_status'], 'ok')
                    for key, epoch in [('spot_last_poll_started_at', start), ('spot_last_poll_completed_at', self.clock.wall)]:
                        self.assertAlmostEqual(datetime.fromisoformat(snapshot[key].replace('Z','+00:00')).timestamp(), epoch, places=3)
                    row = self.csv_row()
                    self.assertAlmostEqual(float(row['spot_poll_duration_ms']), 200, places=5)
                    self.assertEqual(row['spot_poll_duration_status'], 'ok')
                    expected.append(snapshot)
        self.assertTrue(await asyncio.to_thread(self.owner.close, 2))
        with self.path.open(encoding='utf-8-sig', newline='') as stream:
            facts = list(csv.DictReader(stream))
        self.assertEqual(len(facts), 35)
        self.assertEqual(len({f['spot_observation_key'] for f in facts}), 35)
        for fact, snapshot in zip(facts, expected):
            self.assertAlmostEqual(float(fact['spot_poll_duration_ms']), 200, places=5)
            self.assertEqual(fact['spot_poll_duration_status'], 'ok')
            for key in ['spot_last_poll_started_at','spot_last_poll_completed_at','spot_raw_payload_hash']:
                self.assertEqual(fact[key], snapshot[key] or '')
        self.assertTrue(self.owner.snapshot()['writes_drained'])
        self.assertEqual(validator.validate_spot_observation_fact_invariants(self.path), [])

    async def test_invalid_original_endpoints_zero_and_publisher_delay(self):
        self.stack.enter_context(patch.object(spot_api, '_spot_diagnostics_snapshot', {
            '_diagnostics_captured_monotonic':1000.0, '_diagnostics_captured_at_epoch':self.clock.wall,
            'diagnostics_source_poll_seq':1}))
        cases = [(1000,1000.2,'ok'), (1000,1000,'ok'), (None,1000.2,'missing_start'),
                 (1000,None,'missing_end'), (1000,999,'negative_elapsed')]
        for endpoint in [True, float('nan'), float('inf'), -float('inf'), -1, '1000']:
            cases.extend([(endpoint,1000.2,'invalid_endpoint'), (1000,endpoint,'invalid_endpoint')])
        self.clock.advance(50)  # Publishing later must not extend the original interval.
        for seq, (start,end,status) in enumerate(cases,1):
            with self.subTest(start=start,end=end):
                snapshot = spot_api._publish_spot_temperature_snapshot(poll_seq=seq,
                    poll_started_at=self.clock.wall, poll_completed_at=self.clock.wall-60,
                    poll_started_monotonic=start, poll_completed_monotonic=end,
                    poll_clock_domain=clock_domain_id(), temp_url='',
                    classification=classify_spot_raw_response(poll_status='success', body=b'500'))
                self.assertEqual(snapshot['spot_poll_duration_status'], status)
                if status == 'ok':
                    self.assertAlmostEqual(snapshot['spot_poll_duration_ms'], (end-start)*1000)
                else:
                    self.assertIsNone(snapshot['spot_poll_duration_ms'])
                fact = fact_module.build_spot_observation_fact(snapshot)
                self.assertEqual(fact['spot_poll_duration_status'], status)
                self.assertEqual(validator.validate_poll_duration_rows(
                    [[fact[key] for key in fact_module.SPOT_OBSERVATION_FACT_COLUMNS]],
                    fact_module.SPOT_OBSERVATION_FACT_COLUMNS), [])
                # An invalid start does not affect temperature's independent completion proof.
                if end == 1000.2:
                    self.clock.mono = 1000.2
                    self.clock.wall -= 60
                    row = self.csv_row()
                    self.assertEqual(float(row['Temperature']), 500)

    async def test_startup_and_cancelled_incomplete_poll_do_not_publish_facts(self):
        startup = spot_api._build_spot_temperature_snapshot_diagnostics(self.clock.wall)
        self.assertIsNone(startup['spot_poll_duration_ms'])
        self.assertEqual(startup['spot_poll_duration_status'], 'not_attempted')
        entered = asyncio.Event()
        async def transport(request):
            entered.set()
            await asyncio.Event().wait()
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
            task = asyncio.create_task(spot_api._refresh_spot_temperature(client))
            await asyncio.wait_for(entered.wait(), 1)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        self.assertIsNone(spot_api.get_spot_temperature_poll_snapshot())
        self.assertTrue(await asyncio.to_thread(self.owner.close, 2))
        if self.path.exists():
            with self.path.open(encoding='utf-8-sig', newline='') as stream:
                self.assertEqual(list(csv.DictReader(stream)), [])

    async def test_original_poll_start_includes_config_work_and_invalid_start_is_not_recreated(self):
        for start, status in [(1000.0, 'ok'), (None, 'missing_start'), (True, 'invalid_endpoint'),
                              (float('nan'), 'invalid_endpoint'), (float('inf'), 'invalid_endpoint')]:
            with self.subTest(start=start):
                self.clock.mono = 1000.0
                first = True
                def monotonic():
                    nonlocal first
                    if first:
                        first = False
                        return start
                    return self.clock.mono
                class ConfigUrl:
                    def __bool__(inner):
                        self.clock.advance(.05)
                        return True
                    def __str__(inner):
                        return 'http://spot.test/output?p=temperature'
                async def transport(request):
                    self.clock.advance(.15)
                    return httpx.Response(200, text='500', request=request)
                clock = SimpleNamespace(time=self.clock.time, monotonic=monotonic, perf_counter=self.clock.perf_counter)
                with patch.object(spot_api, 'time', clock), patch.object(spot_api.config, 'SPOT_URL', ConfigUrl()):
                    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
                        await spot_api._refresh_spot_temperature(client)
                snapshot = spot_api.get_spot_temperature_poll_snapshot()
                self.assertEqual(snapshot['spot_poll_duration_status'], status)
                if status == 'ok':
                    self.assertAlmostEqual(snapshot['spot_poll_duration_ms'], 200, places=5)
                else:
                    self.assertIsNone(snapshot['spot_poll_duration_ms'])
                self.assertEqual(float(self.csv_row()['Temperature']), 500)

    async def test_missing_and_foreign_duration_domain_do_not_hide_valid_temperature(self):
        for seq, domain in enumerate([None, '', 'foreign-domain'], 1):
            with self.subTest(domain=domain):
                snapshot = spot_api._publish_spot_temperature_snapshot(poll_seq=seq,
                    poll_started_at=self.clock.wall, poll_completed_at=self.clock.wall,
                    poll_started_monotonic=self.clock.mono-.2, poll_completed_monotonic=self.clock.mono,
                    poll_clock_domain=domain, temp_url='',
                    classification=classify_spot_raw_response(poll_status='success', body=b'500'))
                self.assertIsNone(snapshot['spot_poll_duration_ms'])
                self.assertEqual(snapshot['spot_poll_duration_status'], 'domain_unknown')
                row = self.csv_row()
                self.assertEqual(row['spot_poll_duration_ms'], '')
                self.assertEqual(float(row['Temperature']), 500)


class DurationContractTests(unittest.TestCase):
    def test_validator_rejects_forged_duration_but_accepts_true_zero(self):
        header = ['spot_poll_duration_ms', 'spot_poll_duration_status']
        for value, status, accepted in [('0','ok',True), ('200','ok',True), ('','missing_start',True),
            ('0','missing_start',False), ('nan','ok',False), ('inf','ok',False), ('-1','ok',False),
            ('','ok',False), ('200','',False), ('','invented',False)]:
            with self.subTest(value=value,status=status):
                self.assertEqual(not validator.validate_poll_duration_rows([[value,status]], header), accepted)

    def test_historical_fact_meaning_manifest_and_rollover_bytes_are_preserved(self):
        from backend.tests.test_spot_observation_fact import SpotObservationFactTests
        for columns, version in [(fact_module.SPOT_OBSERVATION_FACT_V1_3_0_COLUMNS, '1.3.0'),
                                 (fact_module.SPOT_OBSERVATION_FACT_V1_2_1_COLUMNS, '1.2.1')]:
            with self.subTest(version=version), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / 'spot_observation_fact.csv'
                fact = SpotObservationFactTests().current_fact_row()
                fact.update(spot_observation_fact_schema_version=version, spot_poll_duration_ms='60200')
                with path.open('w',encoding='utf-8-sig',newline='') as stream:
                    writer = csv.DictWriter(stream, fieldnames=columns, extrasaction='ignore')
                    writer.writeheader()
                    writer.writerow(fact)
                old = path.read_bytes()
                self.assertEqual(validator.validate_spot_observation_fact_invariants(path), [])
                manifest = fact_module.build_spot_observation_fact_manifest(fact_path=path, enabled=True,
                    write_failure_count=0, spool_pending_count=0)
                self.assertEqual(manifest['schema_version'], version)
                self.assertEqual(manifest['required_columns'], columns)
                self.assertNotIn('spot_poll_duration', manifest)
                if version == '1.3.0':
                    # Historical v1.3 still enforces diagnostic/provenance integrity.
                    invalid = dict(fact, diagnostics_source_poll_seq='100')
                    with path.open('w',encoding='utf-8-sig',newline='') as stream:
                        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction='ignore')
                        writer.writeheader(); writer.writerow(invalid)
                    self.assertTrue(validator.validate_spot_observation_fact_invariants(path))
                    path.write_bytes(old)  # Synthetic fixture only.
                writer = SpotObservationFactWriter(path)
                self.assertIsNotNone(writer.write_fact({'spot_service_instance_id':'new-service', 'spot_poll_seq':1,
                    'spot_last_poll_completed_at':'2026-09-21T00:00:00Z',
                    'spot_poll_duration_ms':200, 'spot_poll_duration_status':'ok'}))
                archives = list(Path(tmp).glob('*.schema-mismatch.csv'))
                self.assertEqual(len(archives), 1)
                self.assertEqual(archives[0].read_bytes(), old)
                with path.open(encoding='utf-8-sig',newline='') as stream:
                    current = list(csv.DictReader(stream))
                self.assertEqual(current[0]['spot_observation_fact_schema_version'], '1.4.0')
                self.assertEqual(current[0]['spot_poll_duration_status'], 'ok')

    def test_all_csv_families_rollover_old_header_and_preserve_old_bytes(self):
        for operational, hardening, old_version, new_version in [(False,False,'2.3.0','2.3.1'),
            (True,False,'2.4.1','2.4.2'), (True,True,'2.5.1','2.5.2')]:
            with self.subTest(version=new_version), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                logger = CSVLoggerService()
                logger.apply_config(log_path=root, auto_save=True, csv_v2_enabled=True,
                    csv_v2_operational_fields_enabled=operational, csv_v2_temperature_hardening_enabled=hardening)
                contract = logger._get_active_v2_contract()
                self.assertEqual(contract.schema_version, new_version)
                old_header = [c for c in contract.columns if c != 'spot_poll_duration_status']
                path = root / 'Factory_Integrated_Log_v2_20260921_000000.csv'
                with path.open('w',encoding='utf-8-sig',newline='') as stream:
                    writer = csv.writer(stream); writer.writerow(old_header)
                    writer.writerow([old_version] + ['']*(len(old_header)-1))
                old = path.read_bytes()
                handle, _ = logger._open_v2_log_file('20260921_000000', 'Factory_Integrated_Log_v2')
                try:
                    self.assertIsNotNone(handle)
                    self.assertNotEqual(logger._current_v2_csv_path, path)
                    self.assertEqual(path.read_bytes(), old)
                    self.assertIsNotNone(validator.V2_NAME_RE.match(logger._current_v2_csv_path.name))
                finally:
                    logger._close_file(handle)
