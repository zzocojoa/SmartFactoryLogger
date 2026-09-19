// Consolidate the existing ledger. No payload mutation, discovery scan or deletion authority.
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const crypto = require('node:crypto');
const {execFileSync} = require('node:child_process');
const {plain, hash, inside, sourceCatalog, assertMigrationStates} = require('./manage-verification-files.cjs');
const {stableKey} = require('./review-dist-artifacts.cjs');
const repo = path.resolve(__dirname, '..');
const registry = path.join(repo, 'verification-files.local.json');
const kind = 'DESKTOP_REMAINING_RETENTION_CONSOLIDATION_V1';
const lower = p => p.toLowerCase();
const relative = p => path.relative(repo, p).replaceAll('\\', '/');
const digest = bytes => crypto.createHash('sha256').update(bytes).digest('hex').toUpperCase();
const member = (p, root) => lower(p) === lower(root) || inside(p, root);

// Locate top-level values without reserializing historical large JSON integers.
function topLevelSpans(text) {
  JSON.parse(text); // Syntax validation, not the representation used for publication.
  const spans = new Map();
  const space = i => { while (/\s/.test(text[i] || '') && i < text.length) i++; return i; };
  function stringEnd(i) {
    for (i++; i < text.length; i++) {
      if (text[i] === '\\') i++;
      else if (text[i] === '"') return i + 1;
    }
    throw Error('Unterminated JSON string');
  }
  function end(i) {
    if (text[i] === '"') return stringEnd(i);
    if (text[i] === '[' || text[i] === '{') {
      let depth = 1;
      for (i++; i < text.length; i++) {
        if (text[i] === '"') i = stringEnd(i) - 1;
        else if (text[i] === '[' || text[i] === '{') depth++;
        else if ((text[i] === ']' || text[i] === '}') && --depth === 0) return i + 1;
      }
      throw Error('Unterminated JSON container');
    }
    while (i < text.length && !/[\s,}]/.test(text[i])) i++;
    return i;
  }
  let i = space(0);
  if (text[i++] !== '{') throw Error('Expected management object');
  while (text[i = space(i)] !== '}') {
    if (text[i] !== '"') throw Error('Expected property');
    const keyEnd = stringEnd(i), key = JSON.parse(text.slice(i, keyEnd));
    if (spans.has(key)) throw Error('Duplicate top-level property');
    i = space(keyEnd);
    if (text[i++] !== ':') throw Error('Expected colon');
    const start = space(i), finish = end(start);
    spans.set(key, {start, end: finish});
    i = space(finish);
    if (text[i] === ',') i++;
    else if (text[i] !== '}') throw Error('Expected property delimiter');
  }
  return spans;
}
function appendAuditText(text, audit) {
  const spans = topLevelSpans(text), edits = [];
  const history = {at: audit.at, kind, audit_id: audit.id, state: audit.state, deleted_files: 0, moved_files: 0};
  for (const [key, value] of [['audits', audit], ['history', history]]) {
    const span = spans.get(key);
    if (!span || text[span.start] !== '[') throw Error('Expected audit/history array');
    const nonempty = text.slice(span.start + 1, span.end - 1).trim().length > 0;
    edits.push({start: span.end - 1, end: span.end - 1, value: (nonempty ? ',' : '') + JSON.stringify(value)});
  }
  const stamp = spans.get('updated_at');
  if (!stamp || text[stamp.start] !== '"') throw Error('Expected update timestamp');
  edits.push({...stamp, value: JSON.stringify(audit.at)});
  let result = text;
  for (const edit of edits.sort((a, b) => b.start - a.start)) result = result.slice(0, edit.start) + edit.value + result.slice(edit.end);
  JSON.parse(result);
  return result;
}

function buildContext(index, tracked) {
  const detailed = new Map(), preserved = new Map();
  const keep = (p, why) => { if (typeof p === 'string') preserved.set(lower(p), why); };
  const reviewKinds = new Set(['DESKTOP_DIST_READONLY_CLASSIFICATION', 'ARTIFACTS_TMP_READONLY_CLASSIFICATION', 'LARGE_ARTIFACTS_READONLY_REVIEW_V1']);
  for (const a of index.audits) {
    if (reviewKinds.has(a.kind)) for (const f of a.files) detailed.set(lower(f.path), {decision: f.decision, audit_id: a.id});
    for (const f of a.preserved_candidates || []) keep(f.path, f.reason);
    if (a.state === 'COMPLETE' && /EXTRACTION_CLEANUP|ISOLATED_TEST_CACHE_CLEANUP/.test(a.kind)) {
      for (const f of a.files) keep(f.keeper, 'KEEP_PRIOR_DELETION_KEEPER');
      for (const f of a.preserved_files) keep(f.path, 'KEEP_PRIOR_PRESERVED_EVIDENCE');
    }
  }
  for (const p of index.plans) for (const f of p.files) keep(typeof f.retained_copy === 'string' ? f.retained_copy : f.retained_copy?.path, 'KEEP_PRIOR_DELETION_KEEPER');
  for (const m of index.migrations) for (const f of m.files) keep(f.destination, 'KEEP_MIGRATED_SERVER_EVIDENCE');
  return {detailed, preserved, tracked};
}
function classify(file, context) {
  const key = lower(file.path), r = file.relative, previous = context.detailed.get(key);
  if (context.tracked.has(key)) return ['KEEP', 'PROTECT_GIT_TRACKED'];
  if (/^(PROTECT_|KEEP_MIGRATED_SERVER_EVIDENCE)/.test(file.ledger_state)) return ['KEEP', file.ledger_state];
  if (context.preserved.has(key)) return ['KEEP', context.preserved.get(key)];
  if (previous?.decision.startsWith('PROTECT_')) return ['KEEP', previous.decision];
  if (previous?.decision.startsWith('HOLD_')) return ['HOLD', previous.decision];
  if (/^backend\/build\/(SmartFactoryBackend|spot-temperature-v25-qa\/work\/validate_csv_v2_shadow)\//.test(r)) {
    if (/\/(warn-[^/]+\.txt|xref-[^/]+\.html)$/.test(r)) return ['KEEP', 'KEEP_BUILD_DIAGNOSTIC_REPORT'];
    return ['REVIEW_CANDIDATE', 'GENERATED_BUILD_INTERMEDIATE_NOT_DELETION_APPROVED'];
  }
  if (r.startsWith('backend/build/')) return ['KEEP', 'KEEP_BUILD_SPEC_OR_UNCLASSIFIED_BUILD_SUPPORT'];
  if (/^\.tmp_chrome_/.test(r)) return ['HOLD', 'PROFILE_ORIGIN_AND_WHOLE_CACHE_UNIT_REVIEW_REQUIRED'];
  if (previous?.decision === 'KEEP_TOOL_ENVIRONMENT_REQUIRES_DEPENDENCY_REVIEW') return ['HOLD', previous.decision];
  if (previous?.decision.startsWith('CANDIDATE_')) return ['HOLD', 'OLD_CANDIDATE_NOT_REAUTHORIZED'];
  if (previous?.decision.startsWith('KEEP_')) return ['KEEP', previous.decision];
  return ['KEEP', file.ledger_state + '_NO_DISPOSAL_PROOF'];
}
function groupFor(file) {
  const parts = file.relative.split('/');
  if (parts[0] === '..') return file.root;
  return path.join(repo, ...parts.slice(0, ['artifacts', '.tmp', '.gstack', 'dist', 'backend', 'release_artifacts'].includes(parts[0]) ? 2 : 1));
}
function totals(files, field = 'decision') {
  const out = {};
  for (const f of files) { const s = out[f[field]] ||= {files: 0, ledger_bytes: 0}; s.files++; s.ledger_bytes += f.bytes; }
  return out;
}

async function review(expected, record) {
  if (process.platform !== 'win32' || os.hostname() !== 'DESKTOP-SS5CURC' || !/^[A-F0-9]{64}$/.test(expected || '')) throw Error('Host/hash mismatch');
  plain(registry);
  const raw = fs.readFileSync(registry, 'utf8');
  if (digest(raw) !== expected) throw Error('External index hash differs');
  const index = JSON.parse(raw);
  assertMigrationStates(index);
  if (index.workspace !== repo || index.host !== os.hostname() || index.plans.some(p => p.state !== 'COMPLETE') || index.migrations.some(m => m.state !== 'COMPLETE') || index.audits.some(a => a.kind === kind)) throw Error('Ledger state differs or classification already recorded');
  const tracked = new Set(execFileSync('git', ['--no-optional-locks', '-c', 'core.fsmonitor=false', 'ls-files', '-z'], {cwd: repo, encoding: 'utf8', windowsHide: true}).split('\0').filter(Boolean).map(p => lower(path.resolve(repo, p))));
  const context = buildContext(index, tracked), catalog = sourceCatalog(), witnesses = [];
  const sources = new Set([...catalog.map(s => s.source), 'scripts/build_spot_temperature_v25_qa_bundle.ps1', 'backend/build_specs/SmartFactoryBackend.spec', 'scripts/finalize-verification-retention.cjs', 'scripts/finalize-verification-retention.test.cjs']);
  for (const source of sources) {
    const p = path.resolve(repo, source); plain(p);
    const snapshot = stableKey(fs.lstatSync(p, {bigint: true})), bytes = fs.readFileSync(p);
    witnesses.push({source, snapshot, sha256: digest(bytes)});
  }
  const buildText = fs.readFileSync(path.join(repo, 'scripts/build_spot_temperature_v25_qa_bundle.ps1'), 'utf8');
  if (!buildText.includes('$workDirectory = Join-Path $repoRoot "backend\\build\\spot-temperature-v25-qa"') || !buildText.includes('--workpath (Join-Path $workDirectory "work")')) throw Error('QA build producer differs');
  const deployText = fs.readFileSync(path.join(repo, 'scripts/deploy.ps1'), 'utf8');
  if (!deployText.includes('PyInstaller --noconfirm --clean build_specs\\SmartFactoryBackend.spec') || !deployText.includes('if (Test-Path "build") { Remove-Item "build" -Recurse -Force }')) throw Error('Backend build producer differs');

  console.log('[1/3] Recheck the exact indexed file paths only. No discovery scan, payload write or server call.');
  const files = [], seen = new Set(), parents = new Map();
  for (const f of index.files) {
    if (path.resolve(f.path) !== f.path || seen.has(lower(f.path)) || !Number.isSafeInteger(f.bytes) || f.bytes < 0) throw Error('Invalid indexed path/size');
    seen.add(lower(f.path));
    const row = {path: f.path, relative: relative(f.path), root: f.root, bytes: f.bytes, ledger_state: f.state};
    [row.decision, row.reason] = classify(row, context);
    row.previous_review = context.detailed.get(lower(f.path)) || null;
    row.deletion_authorized = false;
    // SFLOps retained release copies are intentionally not probed under this standard token.
    if (index.protected_roots.some(r => member(f.path, r.path))) {
      row.observation = 'NOT_READ_PROTECTED_SCOPE'; row.retention = 'PRESERVE'; row.decision = 'HOLD';
    } else {
      try {
        const parent = path.dirname(f.path);
        if (!parents.has(parent)) { plain(parent); parents.set(parent, stableKey(fs.lstatSync(parent, {bigint: true}))); }
        const s = fs.lstatSync(f.path, {bigint: true});
        if (!s.isFile() || s.isSymbolicLink() || s.nlink !== 1n) throw Error('TYPE_OR_LINK');
        row.snapshot = stableKey(s);
        row.observed_bytes = Number(s.size);
        row.observation = row.observed_bytes === f.bytes ? 'PRESENT_SIZE_MATCH' : 'SIZE_CHANGED';
        if (row.observation !== 'PRESENT_SIZE_MATCH') row.decision = 'HOLD';
      } catch (e) { row.observation = 'UNREADABLE_OR_UNSAFE'; row.error_code = e.code || e.message; row.decision = 'HOLD'; }
    }
    files.push(row);
    if (files.length % 10000 === 0) console.log(`[METADATA] ${files.length}/${index.files.length}`);
  }
  console.log('[2/3] Hash only generated intermediate candidates; retain manifests, reports, profiles, recovery and prior keepers.');
  for (const f of files.filter(f => f.decision === 'REVIEW_CANDIDATE')) f.sha256 = await hash(f.path);
  for (const f of files.filter(f => f.snapshot)) {
    try { if (stableKey(fs.lstatSync(f.path, {bigint: true})) !== f.snapshot) { f.observation = 'CHANGED_DURING_REVIEW'; f.decision = 'HOLD'; } }
    catch (e) { f.observation = 'UNREADABLE_AT_RECHECK'; f.error_code = e.code; f.decision = 'HOLD'; }
  }
  for (const [p, snapshot] of parents) if (stableKey(fs.lstatSync(p, {bigint: true})) !== snapshot) throw Error('Parent changed during review');
  for (const w of witnesses) if (stableKey(fs.lstatSync(path.resolve(repo, w.source), {bigint: true})) !== w.snapshot || await hash(path.resolve(repo, w.source)) !== w.sha256) throw Error('Source witness changed');
  const groupMap = new Map();
  for (const f of files) { const group = groupFor(f); if (!groupMap.has(group)) groupMap.set(group, []); groupMap.get(group).push(f); }
  const groups = [...groupMap].map(([root, entries]) => ({root, files: entries.length, ledger_bytes: entries.reduce((n, f) => n + f.bytes, 0), decisions: totals(entries), observations: totals(entries, 'observation')})).sort((a, b) => b.ledger_bytes - a.ledger_bytes);
  const audit = {id: crypto.randomUUID(), kind, at: new Date().toISOString(), state: 'CLASSIFIED_KNOWN_INVENTORY_NOT_DELETION_APPROVED', original_index_sha256: expected, original_updated_at: index.updated_at,
    scope: 'Only the exact files already registered; no new file discovery or whole-disk completeness claim.', files, groups, summary: totals(files), observations: totals(files, 'observation'), source_catalog: catalog, source_witnesses: witnesses,
    next_review: {paths: files.filter(f => f.decision === 'REVIEW_CANDIDATE').map(f => f.path), producer_sources: ['scripts/build_spot_temperature_v25_qa_bundle.ps1', 'scripts/deploy.ps1', 'backend/build_specs/SmartFactoryBackend.spec'], required_before_deletion: ['Fresh complete unit inventory with membership/hash/ADS/reparse/ACL and exclusive-open checks', 'Live processes/services/tasks/shortcuts and static consumers', 'Preserve build spec, warn/xref reports, final QA bundle, current backend/frontend package inputs', 'Exact deletion list and separate approval; no historical result or current program changes']},
    coverage_gaps: {previous_partial_roots: index.roots.filter(r => r.state === 'PARTIAL').map(r => r.path), previous_links_not_followed: index.links.map(l => l.path), protected_roots_not_scanned: index.protected_roots.map(r => r.path)},
    limitations: ['Ledger sizes are not recovered-space estimates. Changed, inaccessible or protected files retain ledger bytes for reconciliation, not fresh content verification.', 'Metadata checks are live, not an atomic snapshot. Only further-review build intermediate candidates are content-hashed this turn.', 'KEEP means retain now, not proof of uniqueness or perpetual retention. Exact duplicate bytes do not override a previous keeper or evidence obligation.', 'Browser test profiles remain mixed cache/state with unresolved producer/live-use coverage; no whole-profile deletion authorization.', 'Source witnesses validate current generation paths, not every historical or external consumer. No builds, installers, observations or device APIs were run.', 'This appends an audit/history item while preserving historical JSON numeric tokens and old inventory/summary; it does not rescan or rewrite old conclusions.'],
    deleted_files: 0, deleted_bytes: 0, moved_files: 0, existing_acl_writes: 0, remote_server_operations: 0, deletion_authorized: false};
  if (files.length !== index.summary.files || files.reduce((n, f) => n + f.bytes, 0) !== index.summary.bytes) throw Error('Ledger totals differ');
  console.log('[3/3] Append classification to the single management file; preserve all existing payload and history.');
  if (await hash(registry) !== expected) throw Error('Concurrent index change');
  if (record) {
    const output = appendAuditText(raw, audit), fd = fs.openSync(registry + '.writing', 'wx');
    try { fs.writeFileSync(fd, output); fs.fsyncSync(fd); } finally { fs.closeSync(fd); }
    if (await hash(registry) !== expected) throw Error('Concurrent index change; preserve .writing');
    fs.renameSync(registry + '.writing', registry);
    if (await hash(registry) !== digest(output)) throw Error('Published index verification differs');
  }
  console.log(JSON.stringify({id: audit.id, recorded: record, summary: audit.summary, observations: audit.observations, candidate_paths: audit.next_review.paths, source_witnesses: witnesses.length, registered_files: files.length, large_groups: groups.filter(g => g.ledger_bytes >= 25000000).length, deleted_files: 0, index_sha256: await hash(registry)}, null, 2));
  return audit;
}
if (require.main === module) {
  const [mode, expected, ...extra] = process.argv.slice(2);
  if (!['--read', '--record'].includes(mode) || extra.length) throw Error('Use --read/--record INDEX_SHA256');
  review(expected, mode === '--record').catch(e => { console.error('RETENTION_REVIEW_HOLD: ' + e.message); process.exitCode = 1; });
}
module.exports = {topLevelSpans, appendAuditText, buildContext, classify, groupFor, totals};
