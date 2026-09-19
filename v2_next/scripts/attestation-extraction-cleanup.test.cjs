'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),path=require('node:path');
const {assertReviewedCleanupStates,attestationExtractionRecords}=require('./manage-verification-files.cjs');
const repo=path.resolve(__dirname,'..');
function complete(){
  const specs=[[1,'verify_extract_attempt2','package_attempt2',12,4963177],[2,'verify_extract','package',18,9881026],[3,'verify_extract','package',24,19655538],[4,'verify_extract','package',30,39123763],[5,'verify_extract','package',36,77984184],[5,'expand_archive_verify','package',36,77984184]];
  return {kind:'DESKTOP_ATTESTATION_EXTRACTION_CLEANUP',state:'COMPLETE',deleted_files:156,deleted_bytes:229591872,deleted_directories:0,existing_acl_writes:0,journal_sha256:'A'.repeat(64),files:specs.flatMap(([n,source,keeper,count,bytes])=>Array.from({length:count},(_,i)=>({path:path.join(repo,'.tmp','internal_extended_running_state_attestation_r'+n,source,'f'+i),keeper:path.join(repo,'.tmp','internal_extended_running_state_attestation_r'+n,keeper,'f'+i),bytes:i?1:bytes-count+1,sha256:'A'.repeat(64)})))};
}
test('pending attestation transaction blocks a rescan',()=>{
  for(const state of ['PREPARED','HOLD','DELETING'])assert.throws(()=>assertReviewedCleanupStates({audits:[{kind:'DESKTOP_ATTESTATION_EXTRACTION_CLEANUP',state}]}));
});
test('156 sources map to 120 protected same-revision keepers',()=>{
  const a=complete();assertReviewedCleanupStates({audits:[a]});
  assert.equal(attestationExtractionRecords({audits:[a]})[0].files.length,156);
  assert.equal(new Set(a.files.map(f=>f.keeper)).size,120);
});
test('changed scope, shared keeper, totals and journal fail closed',()=>{
  for(const change of [
    a=>a.files.pop(),a=>a.files[0].path=repo,a=>a.files[0].path=a.files[1].path,
    a=>a.files[0].keeper=a.files[12].keeper,a=>a.deleted_files=0,
    a=>a.files[0].sha256='bad',a=>a.files[0].bytes++,a=>a.files[120].sha256='B'.repeat(64),
    a=>a.files[0].path=a.files[0].path.replace('verify_extract_attempt2','verify_extract'),
    a=>a.files[0].path+=':ads',a=>a.journal_sha256='bad',a=>a.deleted_directories=1,
    a=>a.existing_acl_writes=1,a=>a.files[0].bytes=0.5
  ]){const a=complete();change(a);assert.throws(()=>attestationExtractionRecords({audits:[a]}));}
  assert.throws(()=>attestationExtractionRecords({audits:[complete(),complete()]}));
});
