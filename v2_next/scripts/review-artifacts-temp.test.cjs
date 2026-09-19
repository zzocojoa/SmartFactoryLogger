'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),path=require('node:path'),fs=require('node:fs');
const {entryPath,classification,matchExtraction,summarize}=require('./review-artifacts-temp.cjs');
const repo=path.resolve(__dirname,'..');
const context=()=>({tracked:new Set(),retained:new Set(),migrated:new Set(),recovery:[],exact:new Map(),problemGroups:new Set()});
const row=relative=>({relative,path:path.join(repo,...relative.split('/')),bytes:10});
test('canonical evidence, recovery and current build inputs never become duplicate deletion candidates',()=>{
  for(const [name,state] of [['artifacts/server-evidence/a.zip','PROTECT_CANONICAL_SERVER_EVIDENCE'],['.tmp/v1026x1/app/a','PROTECT_CURRENT_HELPER_BUILD_INPUT_AND_RELEASE'],['artifacts/v1026-release-prep-d7a1b20-20260911/a','PROTECT_CURRENT_HELPER_BUILD_INPUT_AND_RELEASE']]){
    const r=row(name),c=context();c.exact.set(r.path,{});assert.equal(classification(r,c),state);
  }
  const r=row('.tmp/recovery/a'),c=context();c.recovery.push(path.dirname(r.path));assert.equal(classification(r,c),'PROTECT_DEPENDENCY_RECOVERY');
});
test('historical cleanup keepers and migrated evidence take precedence over new duplicates',()=>{
  const r=row('.tmp/old/destination/a'),c=context();c.exact.set(r.path,{});c.retained.add(r.path.toLowerCase());assert.equal(classification(r,c),'PROTECT_PREVIOUS_CLEANUP_KEEPER');
  c.retained.clear();c.migrated.add(r.path.toLowerCase());assert.equal(classification(r,c),'PROTECT_MIGRATED_SERVER_EVIDENCE');
});
test('unknown names and links cannot prove disposability',()=>{
  const r=row('.tmp/old/HOLD.zip'),c=context();assert.equal(classification(r,c),'KEEP_PACKAGE_OR_BINARY_NOT_YET_REVIEWED');c.problemGroups.add('.tmp/old');assert.equal(classification(r,c),'HOLD_LINKED_OR_PARTIAL_GROUP');
});
test('canonical entry resolver rejects traversal, ADS and alternate separators',()=>{
  const root=path.join(repo,'.tmp','fixture');assert.equal(entryPath(root,'release/a.txt'),path.join(root,'release','a.txt'));
  for(const n of ['../x','/x','a//b','C:/x','a\\b','a:stream','a. /x','a/..',''])assert.throws(()=>entryPath(root,n));
});
test('matching requires one complete 32-member revision, including exact relative names',()=>{
  const files=Array.from({length:32},(_,i)=>({name:'f'+i,path:'source'+i,bytes:i,sha256:'HASH'+i}));
  const pool={root:'retained',archive:{},files:files.map(f=>({...f,path:'keep/'+f.name}))};
  assert.equal(matchExtraction(files,[pool]).length,32);assert.equal(matchExtraction(files.slice(1),[pool]),null);
  for(const delta of [{bytes:999},{sha256:'other'},{name:'F0'}])assert.equal(matchExtraction([{...files[0],...delta},...files.slice(1)],[pool]),null);
  assert.equal(matchExtraction(files,[{...pool,files:pool.files.slice(0,16)},{...pool,files:pool.files.slice(16)}]),null);
});
test('summary partitions readable bytes without calling all kept files hash-verified',()=>{
  const files=[{...row('.tmp/a/one'),decision:'CANDIDATE_EXACT_TEST_EXTRACTION_PENDING_DELETE_REVIEW'},{...row('artifacts/b/two'),decision:'KEEP_UNRESOLVED_REQUIRES_REVIEW'}];
  const s=summarize(files);assert.equal(s.readable_files,2);assert.equal(s.logical_bytes,20);assert.equal(s.groups['.tmp/a'].candidate_bytes,10);
});
test('review has no candidate deletion, copied output, ACL changes or helper execution',()=>{
  const code=fs.readFileSync(path.join(__dirname,'review-artifacts-temp.cjs'),'utf8');
  assert.doesNotMatch(code,/fs\.(?:unlink|rm|rmdir|copyFile)|Remove-Item|Set-Acl|Invoke-RestMethod|Start-Process/);
  assert.match(code,/deletion_authorized:false/);assert.match(code,/registry\+'\.writing'/);
});
