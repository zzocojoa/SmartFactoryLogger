'use strict';
// Uses the uploaded inventory as a read-only fixture; all mutations below are in memory.
const fs = require('node:fs');
const assert = require('node:assert/strict');
const { analyze, hash, csv, EXPECTED_SHA } = require('./review-cleanup-inventory.cjs');
const bytes = fs.readFileSync(process.argv[2]);
assert.equal(hash(bytes), EXPECTED_SHA);
const doc = JSON.parse(bytes.toString('utf8'));
let passed = 0;
function check(name, test) { test(); passed++; console.log('PASS ' + name); }
function rejects(object, property, value) {
  const prior = object[property];
  try { object[property] = value; assert.throws(() => analyze(doc)); }
  finally { object[property] = prior; }
}
check('independent exact totals', () => assert.equal(analyze(doc).summary.measured_bytes, 14268914446));
check('null means unmeasured, not zero', () => assert.equal(analyze(doc).rows.filter(r => r.logical_bytes === null).length, 5));
check('no executable deletion authorization', () => assert.ok(analyze(doc).rows.every(r => r.deletion_authorized === false)));
check('mixed backup exclusions', () => assert.equal(analyze(doc).rows.find(r => r.id === 44).reviewed_classification, 'MIXED_OR_RECOVERY_REVIEW'));
check('duplicate entry rejected', () => rejects(doc.entries[1], 'path', doc.entries[0].path));
check('orphan entry rejected', () => rejects(doc.entries[1], 'group', 9999));
check('path outside its group rejected', () => rejects(doc.entries[1], 'path', 'C:/not-the-group'));
check('file count mismatch rejected', () => rejects(doc.groups[1], 'files', doc.groups[1].files + 1));
check('unknown classifier rejected', () => rejects(doc.groups[1], 'classification', 'DELETE_NOW'));
check('protected size converted to zero rejected', () => rejects(doc.groups[0], 'logical_bytes', 0));
check('authorized source row rejected', () => rejects(doc.groups[1], 'deletion_authorized', true));
check('duplicate group id rejected', () => rejects(doc.groups[1], 'id', doc.groups[0].id));
check('incomplete discovery rejected', () => rejects(doc.discovery[0], 'status', 'PARTIAL'));
check('CSV quoting and null representation', () => {
  assert.equal(csv([{ value: 'a,"b"', missing: null }]), '\uFEFF"value","missing"\r\n"a,""b""",""\r\n');
});
assert.equal(hash(fs.readFileSync(process.argv[2])), EXPECTED_SHA);
console.log(`OFFLINE_REVIEW_TEST_PASS count=${passed}; no source writes or server access`);
