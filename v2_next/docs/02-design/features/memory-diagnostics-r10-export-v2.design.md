# Memory Diagnostics R10 Export V2 Design

## 1. Summary

`memory-diagnostics-r10-export-v2`는 memory export를 forensic artifact로 확장한다. export는 운영 분석에 충분해야 하지만 민감정보를 저장하지 않아야 한다.

## 2. Files

- `backend/Observability/memory_service.py`
- `backend/app.py`
- frontend export caller
- backend export tests
- frontend export tests if applicable

## 3. Schema Design

Top-level payload:

```text
schema_version: memory-export-v2
generated_at
runtime
summary_state
details_state
frontend
analysis
redaction
```

`analysis` includes:

- `budget_results`
- `leak_suspects`
- `collector_runtime_state`
- `last_gc_snapshot`
- profiler state/diff

Service accessors or equivalent methods:

```text
get_budget_results()
get_leak_suspects()
get_collector_runtime_state()
get_last_gc_snapshot()
```

## 4. Runtime Design

Runtime block includes:

- pid
- python version
- platform
- argv after redaction

## 5. Redaction Design

Recursive key-based redaction applies to dictionaries and arrays.

Sensitive key fragments:

```text
password
token
secret
authorization
api_key
private_key
```

SPOT live URL 원문은 저장하지 않는다.

## 6. Tests

- schema v2 contains runtime and analysis
- sensitive keys are redacted recursively
- export succeeds without frontend snapshot
- frontend Electron snapshot is included when provided

## 7. Analyze Evidence

bkit analyze는 schema fields, redaction helper, export endpoint integration, tests, sanitized export smoke evidence를 확인해야 한다.
