'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),path=require('node:path');
const {buildIntermediateRecords,assertReviewedCleanupStates}=require('./manage-verification-files.cjs');
const repo=path.resolve(__dirname,'..'),root=path.join(repo,'backend','build');
function fixture(){return {audits:[{kind:'DESKTOP_BUILD_INTERMEDIATE_CLEANUP',state:'COMPLETE',deleted_files:17,deleted_bytes:36648177,deleted_directories:0,existing_acl_writes:0,journal_sha256:'A'.repeat(64),
  files:Array.from({length:17},(_,i)=>({path:path.join(root,`file${i}.bin`),bytes:i?1:36648161,sha256:'B'.repeat(64)})),
  preserved_files:Array.from({length:14},(_,i)=>({path:path.join(root,`history${i}.toc`),sha256:'C'.repeat(64)}))}]};}
test('completed record accepted',()=>assert.equal(buildIntermediateRecords(fixture()).length,1));
for(const [name,mutate] of Object.entries({pending:a=>a.state='PREPARED',count:a=>a.deleted_files=18,bytes:a=>a.deleted_bytes++,acl:a=>a.existing_acl_writes=1,directory:a=>a.deleted_directories=1,journal:a=>a.journal_sha256='bad',duplicate:a=>a.files[1]=a.files[0],escape:a=>a.files[0].path=path.join(repo,'keep.bin'),toc:a=>a.files[0].path=path.join(root,'Analysis-00.toc'),overlap:a=>a.preserved_files[0]=a.files[0],hash:a=>a.files[0].sha256='bad'})){
  test('reject '+name,()=>{const f=fixture();mutate(f.audits[0]);assert.throws(()=>buildIntermediateRecords(f));});
}
test('pending cleanup blocks rescan',()=>{const f=fixture();f.audits[0].state='PREPARED';assert.throws(()=>assertReviewedCleanupStates(f));});
test('ambiguous duplicate cleanup rejected',()=>{const f=fixture();f.audits.push(f.audits[0]);assert.throws(()=>buildIntermediateRecords(f));});
