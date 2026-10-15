"""Bind observed CSV identity to closed files; no shutdown or full CSV validation.

The protected caller must authenticate the successful observation result and its
expectation file. Self-consistent files alone do not prove a field run or approval.
"""
import hashlib
import os
import re
import time
from uuid import UUID

import field_configuration_binding as configuration
import field_installation_binding as binding
from field_resource_sampling import error_record


SCHEMA = 'sfl-field-shutdown-expectation-v1'
SUPPORTED_SCHEMAS = ('2.5.0', '2.5.1', '2.5.2')


def positive_sequence(value):
    return type(value) is int and 0 < value <= 2**63 - 1


def validate_expectation(expected, *, candidate=binding.CANDIDATE_1028):
    binding.require(type(candidate) is binding.CandidateIdentity, 'candidate-identity-type')
    candidate.validate()
    binding.require(isinstance(expected, dict) and expected.get('schema') == SCHEMA,
                    'shutdown-expectation-schema')
    binding.require(expected.get('build_git_commit') == candidate.commit, 'shutdown-expectation-build')
    for key in ('logger_service_instance_id', 'spot_service_instance_id'):
        value = expected.get(key)
        binding.require(isinstance(value, str) and str(UUID(value)) == value, 'shutdown-expectation-uuid')
    name = expected.get('csv_file_name')
    binding.require(isinstance(name, str) and len(name) <= 150
                    and re.fullmatch(r'Factory_Integrated_Log_v2_[A-Za-z0-9_.-]+\.csv', name),
                    'shutdown-expectation-filename')
    binding.require(expected.get('schema_version') in SUPPORTED_SCHEMAS, 'shutdown-expectation-csv-schema')
    binding.require(positive_sequence(expected.get('minimum_sample_seq')), 'shutdown-expectation-sequence')
    binding.require(isinstance(expected.get('health_body_sha256'), str)
                    and re.fullmatch('[0-9a-f]{64}', expected['health_body_sha256']),
                    'shutdown-expectation-health-hash')
    binding.require(configuration.utc_timestamp(expected.get('observed_at')) <= time.time() + 2,
                    'shutdown-expectation-future-time')


def expectation_from_boundary(boundary, backend, *, candidate=binding.CANDIDATE_1028):
    """Use the exact final health bytes, not a second unbound HTTP request."""
    binding.require(boundary.get('binding_status') == 'PASS', 'shutdown-boundary-not-passed')
    raw = bytes.fromhex(boundary['health_body_hex'])
    record = boundary['health_record']
    binding.require(record.get('request_success') is True and len(raw) == record.get('body_bytes')
                    and hashlib.sha256(raw).hexdigest() == record.get('body_sha256'),
                    'shutdown-health-body-binding')
    health = binding.strict_json(raw)
    sessions = binding.runtime_sessions(health, backend, candidate=candidate)
    binding.require(sessions == boundary.get('sessions'), 'shutdown-boundary-sessions')
    operational = health['spot_temperature']['v2_4_operational']
    expected = dict(schema=SCHEMA, build_git_commit=candidate.commit, **sessions,
                    schema_version=operational.get('schema_version'),
                    csv_file_name=operational.get('current_v2_csv_file_name'),
                    minimum_sample_seq=operational.get('last_sample_seq'),
                    health_body_sha256=record['body_sha256'], observed_at=boundary.get('observed_at'))
    validate_expectation(expected, candidate=candidate)
    return expected


def review_metadata(metadata, expected, expected_configuration, *, candidate=binding.CANDIDATE_1028):
    """Check metadata claims. CSV contents and actual process exit remain gates."""
    validate_expectation(expected, candidate=candidate)
    binding.require(configuration.review_snapshot(expected_configuration, candidate=candidate)['status'] == 'PASS',
                    'shutdown-configuration-reference-invalid')
    issues = []
    if not isinstance(metadata, dict):
        metadata = {}
        issues.append('metadata-object-missing')
    sections = {}
    for key in ('schema_metadata', 'spot_configuration_snapshot', 'csv_closeout'):
        value = metadata.get(key)
        if not isinstance(value, dict):
            issues.append('metadata-section:' + key)
            value = {}
        sections[key] = value
    schema = sections['schema_metadata']
    snapshot = sections['spot_configuration_snapshot']
    closeout = sections['csv_closeout']

    def check(condition, reason):
        if not condition:
            issues.append(reason)

    check(schema.get('git_commit') == expected['build_git_commit'], 'schema-build')
    check(snapshot.get('build_git_commit') == expected['build_git_commit'], 'configuration-build')
    check(schema.get('logger_service_instance_id') == expected['logger_service_instance_id'], 'schema-logger')
    check(closeout.get('logger_service_instance_id') == expected['logger_service_instance_id'], 'closeout-logger')
    check(schema.get('schema_version') == expected['schema_version']
          and schema.get('active_schema_version') == expected['schema_version'], 'csv-schema')
    check(schema.get('csv_v2_temperature_hardening_enabled') is True, 'hardening-disabled')
    check(closeout.get('finalized') is True, 'closeout-not-finalized')
    check(closeout.get('closeout_reason') == 'shutdown', 'closeout-not-shutdown')
    check(closeout.get('csv_file_name') == expected['csv_file_name'], 'closeout-filename')
    sequence = closeout.get('final_persisted_sample_seq')
    check(positive_sequence(sequence) and sequence >= expected['minimum_sample_seq'], 'closeout-sequence')
    try:
        # This is last persistence time, NOT shutdown time. It can precede health.
        check(configuration.utc_timestamp(closeout.get('persisted_at')) <= time.time() + 2,
              'closeout-persistence-future')
    except (ValueError, OverflowError):
        issues.append('closeout-persistence-time')
    config_review = configuration.review_snapshot(snapshot, expected_configuration, candidate=candidate)
    return dict(status='PASS' if not issues and config_review['status'] == 'PASS' else 'FAIL',
                identity_status='FAIL' if issues else 'PASS', issues=issues,
                configuration_review=config_review, field_gate='NOT_EVALUATED',
                csv_content_gate='NOT_EVALUATED', normal_shutdown_gate='NOT_EVALUATED',
                release_gate='HOLD', promotion_allowed=False)


def review_shutdown_files(data_directory, expected, reference_path, reference_sha256, *, candidate=binding.CANDIDATE_1028):
    """Read exact names under locks; only publish PASS after all contexts close.

    No scan for a replacement sidecar and no app/process/setting mutations.
    Subsequent full validation must bind its input bytes to the returned facts.
    """
    result = dict(shutdown_binding_status='FAIL', files={}, errors=[], field_gate='NOT_EVALUATED',
                  csv_content_gate='NOT_EVALUATED', normal_shutdown_gate='NOT_EVALUATED',
                  release_gate='HOLD', promotion_allowed=False,
                  scope='OBSERVED_IDENTITY_AND_CONFIGURATION_TO_DEFAULT_STREAM_FILES')
    try:
        validate_expectation(expected, candidate=candidate)
        directory = binding.plain_path(data_directory)
        csv_path = directory / expected['csv_file_name']
        metadata_path = csv_path.with_suffix('.metadata.json')
        with configuration.configuration_reference(reference_path, reference_sha256, candidate=candidate) as config, \
                binding.locked_read(csv_path) as csv_stream, binding.locked_read(metadata_path) as metadata_stream:
            streams = [(csv_path, csv_stream, 2 * 1024**3), (metadata_path, metadata_stream, 4 * 1024**2)]
            identities = {}
            for path, stream, limit in streams:
                stat = os.fstat(stream.fileno())
                binding.require(0 < stat.st_size <= limit, 'shutdown-file-size-budget')
                identities[path] = (stat.st_dev, stat.st_ino, stat.st_size)
                result['files'][path.name] = dict(path=str(path), **binding.stream_fact(stream))
            metadata_stream.seek(0)
            metadata = binding.strict_json(metadata_stream.read(4 * 1024**2 + 1))
            result['review'] = review_metadata(metadata, expected, config, candidate=candidate)
            for path, stream, _ in streams:
                current = binding.plain_path(path).stat()
                binding.require((current.st_dev, current.st_ino, current.st_size) == identities[path],
                                'shutdown-file-identity-changed')
                fact = result['files'][path.name]
                binding.require(binding.stream_fact(stream) == dict(bytes=fact['bytes'], sha256=fact['sha256']),
                                'shutdown-file-bytes-changed')
        result['configuration_reference_sha256'] = reference_sha256
        result['shutdown_binding_status'] = result['review']['status']
    except Exception as error:
        result['errors'].append(error_record(error))
    return result
