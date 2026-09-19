'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {selectGroups,extractionSpecs,exactTree,cacheCategory,decide,totals}=require('./review-large-verification-files.cjs');
const context=()=>({protected:new Set(),tracked:new Set(),problemGroups:new Set(),exact:new Map()});
const row=relative=>({path:path.resolve(__dirname,'..',relative),relative,group:relative.split('/').slice(0,2).join('/'),bytes:12});
test('large unresolved selection excludes already protected/retained delivery and tiny groups',()=>{
  assert.deepEqual(selectGroups([
    {relative:'.tmp/a/one',bytes:25000000,decision:'KEEP_PACKAGE_OR_BINARY_NOT_YET_REVIEWED'},
    {relative:'artifacts/b/one',bytes:250000000,decision:'PROTECT_DEPENDENCY_RECOVERY'},
    {relative:'artifacts/c/one',bytes:1,decision:'KEEP_EVIDENCE_NOT_PROVEN_DISPOSABLE'},
    {relative:'artifacts/d/one',bytes:250000000,decision:'KEEP_HASH_BOUND_STAGE_DELIVERY'}
  ]),['.tmp/a']);
});
test('producer-backed extraction scope excludes old attempts and unbound r4 independent extraction',()=>{
  const specs=extractionSpecs();assert.equal(specs.length,6);
  assert.equal(specs[0].source,'verify_extract_attempt2');assert.equal(specs[0].keeper,'package_attempt2');
  assert.equal(specs.filter(s=>s.source==='expand_archive_verify').length,1);
  assert.equal(specs.at(-1).root,'.tmp/internal_extended_running_state_attestation_r5');
});
test('complete tree comparison rejects missing, extra, changed, renamed and duplicate members',()=>{
  const a=[{name:'a',path:'src/a',bytes:1,sha256:'A'},{name:'dir/b',path:'src/dir/b',bytes:2,sha256:'B'}],b=a.map(f=>({...f,path:'keep/'+f.name}));
  assert.equal(exactTree(a,b)[0].retained_copy.path,'keep/a');
  for(const rows of [[],a.slice(1),[...a,a[0]],[{...a[0],sha256:'C'},a[1]],[{...a[0],bytes:3},a[1]],[{...a[0],name:'A'},a[1]]])assert.equal(exactTree(rows,b),null);
});
test('prior keepers, tracked files and link boundaries override exact duplicate matches',()=>{
  const f=row('.tmp/x/verify_extract/a'),c=context();c.exact.set(f.path,{});assert.equal(decide(f,c),'CANDIDATE_EXACT_VERIFICATION_EXTRACTION');
  c.problemGroups.add(f.group);assert.equal(decide(f,c),'HOLD_LINKED_OR_PARTIAL_GROUP');
  c.tracked.add(f.path.toLowerCase());assert.equal(decide(f,c),'PROTECT_GIT_TRACKED');
  c.protected.add(f.path.toLowerCase());assert.equal(decide(f,c),'PROTECT_PRIOR_KEEPER_OR_RECOVERY');
});
test('test cache recognition is restricted to known isolated run profile paths',()=>{
  const prefix='artifacts/operator-emphasis-optimization-20260910/run-AB12/electron-profile/';
  for(const unit of ['Cache','Code Cache','GPUCache','Dictionaries'])assert.equal(cacheCategory(prefix+unit+'/file'),unit);
  for(const p of ['AppData/Roaming/profile/Cache/a',prefix+'Local Storage/leveldb/a',prefix+'CacheBogus/a'])assert.equal(cacheCategory(p),null);
  assert.equal(decide(row(prefix+'Cache/a'),context()),'HOLD_TEST_CACHE_UNIT_AND_LIVE_USE_REVIEW');
  assert.equal(decide(row(prefix+'Preferences'),context()),'KEEP_TEST_PROFILE_STATE_NOT_CACHE');
});
test('package inputs, older attempt origins and diagnostic records remain kept',()=>{
  assert.equal(decide(row('.tmp/internal_extended_running_state_attestation_r1/package_attempt2/a'),context()),'KEEP_ATTESTATION_BUILD_INPUT_AND_LINEAGE');
  assert.equal(decide(row('.tmp/internal_extended_running_state_attestation_r2/verify_extract_initial/a'),context()),'KEEP_OTHER_EXTRACTION_ORIGIN_NOT_ESTABLISHED');
  assert.equal(decide(row('artifacts/runtime_validation_20260720_080101_review/spot_tcp_brief_redacted.txt'),context()),'KEEP_DIAGNOSTIC_OR_REPLAY_EVIDENCE');
});
test('state totals partition bytes without treating whole scope as deletion candidates',()=>{
  const s=totals([{decision:'KEEP',bytes:100},{decision:'CANDIDATE',bytes:20},{decision:'KEEP',bytes:7}]);assert.deepEqual(s,{KEEP:{files:2,bytes:107},CANDIDATE:{files:1,bytes:20}});
});
test('auditor cannot delete/copy payload, change ACLs or execute observed helpers',()=>{
  const code=fs.readFileSync(path.join(__dirname,'review-large-verification-files.cjs'),'utf8');
  assert.doesNotMatch(code,/fs\.(?:unlink|rm|rmdir|copyFile)|Remove-Item|Set-Acl|Invoke-RestMethod|Start-Process/);
  assert.match(code,/deletion_authorized:false/);assert.match(code,/registry\+'\.writing'/);assert.match(code,/execFileSync\('git'/);
});
