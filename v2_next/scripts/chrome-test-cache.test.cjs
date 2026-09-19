'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),path=require('node:path');
const {chromeTestProfileSpecs,chromeCacheUnit,chromeTestCacheRecords,assertReviewedCleanupStates}=require('./manage-verification-files.cjs');
function fixture(){const files=[],preserved_files=[];for(const s of chromeTestProfileSpecs()){
  for(let i=0;i<s.deleted_files;i++)files.push({path:path.join(s.root,'Default','Cache','Cache_Data','f_'+i.toString(16).padStart(6,'0')),bytes:i?1:s.deleted_bytes-s.deleted_files+1,sha256:'A'.repeat(64),unit:path.join(s.root,'Default','Cache'),disposition:'DELETE_CACHE'});
  const n=s.files-s.deleted_files;for(let i=0;i<n;i++)preserved_files.push({path:path.join(s.root,'RetainedFixture',String(i)),bytes:i?1:s.bytes-s.deleted_bytes-n+1,sha256:'B'.repeat(64),disposition:'KEEP_PROFILE_STATE'});
}return {audits:[{kind:'DESKTOP_CHROME_TEST_CACHE_CLEANUP',state:'COMPLETE',files,preserved_files,deleted_files:642,deleted_bytes:211061627,deleted_directories:0,existing_acl_writes:0,journal_sha256:'C'.repeat(64)}]};}
test('complete fixed cache scope accepted',()=>assert.equal(chromeTestCacheRecords(fixture()).length,1));
test('retention consolidation respects protected browser state',()=>{
  const {classify}=require('./finalize-verification-retention.cjs');
  const f={path:path.join(chromeTestProfileSpecs()[0].root,'Default','Cookies'),relative:'.tmp_chrome_cdp_settings_lazy/Default/Cookies',ledger_state:'PROTECT_RETAINED_BROWSER_PROFILE'};
  assert.deepEqual(classify(f,{tracked:new Set(),detailed:new Map(),preserved:new Map()}),['KEEP','PROTECT_RETAINED_BROWSER_PROFILE']);
});
for(const [name,mutate] of Object.entries({pending:a=>a.state='PREPARED',count:a=>a.deleted_files++,bytes:a=>a.deleted_bytes++,acl:a=>a.existing_acl_writes++,directory:a=>a.deleted_directories++,journal:a=>a.journal_sha256='bad',duplicate:a=>a.files[1]=a.files[0],outside:a=>a.files[0].path=path.join(__dirname,'keep'),cookie:a=>a.files[0].path=path.join(chromeTestProfileSpecs()[0].root,'Default','Cookies'),hash:a=>a.files[0].sha256='bad',drift:a=>a.files[0].bytes++,overlap:a=>a.preserved_files[0]=a.files[0],swap:a=>{[a.files[0],a.preserved_files[0]]=[a.preserved_files[0],a.files[0]];}}))test('reject '+name,()=>{const f=fixture();mutate(f.audits[0]);assert.throws(()=>chromeTestCacheRecords(f));});
test('pending blocks rescan',()=>{const f=fixture();f.audits[0].state='PREPARED';assert.throws(()=>assertReviewedCleanupStates(f));});
test('multiple audits rejected',()=>{const f=fixture();f.audits.push(f.audits[0]);assert.throws(()=>chromeTestCacheRecords(f));});
for(const p of ['Default\\Cookies','Default\\Local Storage\\file','Default\\Service Worker\\CacheStorage\\file','Dictionaries\\dictionary','Default\\Cache-copy\\Cache_Data\\index'])test('retain '+p,()=>assert.equal(chromeCacheUnit(p),null));
for(const p of ['Default\\Cache\\unknown','Default\\GPUCache\\data_4','Default\\Cache\\..\\Cookies','Default\\Cache\\Cache_Data\\index:stream'])test('reject unknown '+p,()=>assert.throws(()=>chromeCacheUnit(p)));
