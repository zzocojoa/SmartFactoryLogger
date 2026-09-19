'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),path=require('node:path');
const {assertReviewedCleanupStates,stageExtractionRecords}=require('./manage-verification-files.cjs');
const repo=path.resolve(__dirname,'..');
function complete(){return {kind:'DESKTOP_STAGE_EXTRACTION_CLEANUP',state:'COMPLETE',deleted_files:64,deleted_bytes:331293866,deleted_directories:0,existing_acl_writes:0,journal_sha256:'A'.repeat(64),files:[4,5].flatMap(n=>Array.from({length:32},(_,i)=>({path:path.join(repo,'.tmp','v26stage-tests-r'+n,'actual-transfer','f'+i),keeper:path.join(repo,'artifacts','v1026-server-stage-20260911-r'+(n-3),'transfer-files','f'+i),bytes:i?1:165646902,sha256:'A'.repeat(64)})))};}
test('pending and interrupted stage cleanup block inventory overwrite',()=>{for(const state of ['PREPARED','HOLD','DELETING'])assert.throws(()=>assertReviewedCleanupStates({audits:[{kind:'DESKTOP_STAGE_EXTRACTION_CLEANUP',state}]}));});
test('completed fixed mappings remain available to scan and verification',()=>{const a=complete();assertReviewedCleanupStates({audits:[a]});assert.equal(stageExtractionRecords({audits:[a]})[0].files.length,64);});
test('source, keeper revision, count and completion mismatches fail closed',()=>{
  for(const change of [a=>a.files.pop(),a=>a.files[0].path=repo,a=>a.files[0].keeper=a.files[32].keeper,a=>a.deleted_files=0,a=>a.files[0].sha256='bad',a=>a.files[0].bytes++]){const a=complete();change(a);assert.throws(()=>stageExtractionRecords({audits:[a]}));}
  assert.throws(()=>stageExtractionRecords({audits:[complete(),complete()]}));
});
