'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {stableKey,protectedReason,classify,selectCopy,summarize}=require('./review-dist-artifacts.cjs');
const make=(relative,sha256='A',bytes=4)=>({path:path.resolve('dist',relative),relative,sha256,bytes});
test('referenced staging trees and tracked sources remain protected even with exact copies',()=>{
  for(const name of ['win-unpacked/app.exe','SmartFactory_Portable/start.bat']){
    const f=make(name);assert.equal(classify(f,{copy:{...f,path:'elsewhere'}}),'PROTECT_REFERENCED_BUILD_TREE');
  }
  assert.equal(classify(make('source.js'),{tracked:true}),'PROTECT_GIT_TRACKED');
  assert.equal(protectedReason('win-unpacked-other/app.exe'),null);
  assert.equal(protectedReason('SmartFactory_Portable.zip'),null);
});
test('complete CI sets are kept and runtime references block all other candidates',()=>{
  const f=make('ci-release/example.exe');assert.equal(classify(f,{copy:{...f,path:'other'}}),'KEEP_COMPLETE_CI_RELEASE_SET');
  assert.equal(classify(make('a.exe'),{runtimeHits:1,copy:{...make('a.exe'),path:'other'}}),'HOLD_OBSERVED_RUNTIME_REFERENCE');
});
test('only verified bytes and a distinct retained path form a candidate',()=>{
  const f=make('a.exe');
  assert.equal(classify(f,{copy:f}),'KEEP_PACKAGE_WITHOUT_VERIFIED_RETAINED_COPY');
  assert.equal(classify(f,{copy:{...f,path:'other',sha256:'B'}}),'KEEP_PACKAGE_WITHOUT_VERIFIED_RETAINED_COPY');
  assert.equal(classify(f,{copy:{...f,path:'other',bytes:5}}),'KEEP_PACKAGE_WITHOUT_VERIFIED_RETAINED_COPY');
  assert.equal(classify(f,{copy:{...f,path:'other'}}),'CANDIDATE_EXACT_DUPLICATE_REQUIRES_REFERENCE_REVIEW');
  assert.equal(classify(make('report.json')),'KEEP_UNIQUE_OR_UNRESOLVED_EVIDENCE');
});
test('retained selection prefers canonical copies and does not use self or changed bytes',()=>{
  const f=make('a.exe'),ci={...make('ci/a.exe'),external:false},canonical={...f,path:path.resolve('evidence','a.exe'),external:true};
  assert.equal(selectCopy(f,[f,{...ci,sha256:'B'},ci,canonical]),canonical);
  assert.equal(selectCopy(f,[f,{...ci,bytes:3}]),null);
});
test('summary counts disjoint files and candidate bytes, not potential disk savings',()=>{
  const a={...make('ci/a.exe'),decision:'KEEP_COMPLETE_CI_RELEASE_SET'},b={...make('a.exe'),decision:'CANDIDATE_EXACT_DUPLICATE_REQUIRES_REFERENCE_REVIEW'};
  const s=summarize([a,b]);assert.equal(s.files,2);assert.equal(s.bytes,8);assert.equal(s.groups['a.exe'].candidate_bytes,4);assert.equal(s.groups.ci.candidate_files,0);
});
test('metadata witness uses precise integer timestamps and file identity',()=>{
  const s={size:4n,mtimeNs:1789768000000000001n,ctimeNs:5n,birthtimeNs:6n,ino:7n,dev:8n,nlink:1n};
  assert.notEqual(stableKey(s),stableKey({...s,mtimeNs:s.mtimeNs+1n}));
  assert.notEqual(stableKey(s),stableKey({...s,ino:9n}));
});
test('review tooling has no deletion or product/network execution and no generic output path',()=>{
  const js=fs.readFileSync(path.join(__dirname,'review-dist-artifacts.cjs'),'utf8');
  const ps=fs.readFileSync(path.join(__dirname,'read-dist-use.ps1'),'utf8');
  assert.doesNotMatch(js,/fs\.(?:rm|unlink|rmdir|chmod|chown|copyFile|mkdir)(?:Sync)?\(/);
  assert.doesNotMatch(ps,/(?:Remove-Item|Stop-Process|Start-Process|Set-Acl|Invoke-WebRequest|Invoke-RestMethod)\b/i);
  assert.match(js,/deletion_authorized:false/);assert.match(js,/assertMigrationStates\(index\)/);assert.match(js,/fs\.openSync\(staging,'wx'\)/);
  assert.match(js,/original_registry_sha256:original/);
});
