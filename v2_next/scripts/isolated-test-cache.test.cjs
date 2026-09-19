'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),path=require('node:path'),fs=require('node:fs');
const {isolatedTestCacheSpecs,isolatedTestCacheRecords,assertReviewedCleanupStates}=require('./manage-verification-files.cjs');
function complete(){
  return {kind:'DESKTOP_ISOLATED_TEST_CACHE_CLEANUP',state:'COMPLETE',deleted_files:181,deleted_bytes:184040248,deleted_directories:0,existing_acl_writes:0,journal_sha256:'A'.repeat(64),
    files:isolatedTestCacheSpecs().flatMap(s=>s.names.map((n,i)=>({path:path.join(s.unit,...n.split('/')),unit:s.unit,category:s.category,bytes:i?1:s.bytes-s.names.length+1,sha256:'A'.repeat(64)}))),
    preserved_files:Array.from({length:419},(_,i)=>({path:'fixture-preserved-'+i,sha256:'B'.repeat(64)}))};
}
test('39 complete cache units; seven profiles; no user-created dictionary or persistent state',()=>{
  const specs=isolatedTestCacheSpecs();assert.equal(specs.length,39);
  assert.equal(new Set(specs.map(s=>path.dirname(s.unit))).size,7);
  assert.equal(specs.reduce((n,s)=>n+s.names.length,0),181);
  assert.equal(specs.reduce((n,s)=>n+s.bytes,0),184040248);
  // The checkout itself may legitimately be under AppData/Local/Temp.
  // Check the managed path below the repository, not its machine-specific parent.
  const repo=path.resolve(__dirname,'..');
  assert.ok(specs.every(s=>!/(Local Storage|Session Storage|Shared Dictionary|Preferences|Custom Dictionary|AppData)/.test(path.relative(repo,s.unit))));
  assert.ok(specs.filter(s=>s.category==='Dictionaries').every(s=>s.names.join()==='ko-3-0.bdic'));
});
test('pending transaction blocks management rescan; completion validates fixed scope',()=>{
  for(const state of ['PREPARED','HOLD','PARTIAL_STOPPED'])assert.throws(()=>assertReviewedCleanupStates({audits:[{kind:'DESKTOP_ISOLATED_TEST_CACHE_CLEANUP',state}]}));
  const a=complete();assertReviewedCleanupStates({audits:[a]});assert.equal(isolatedTestCacheRecords({audits:[a]}).length,1);
});
test('partial unit, unexpected paths, mismatched counts and overlap fail closed',()=>{
  for(const mutate of [
    a=>a.files.pop(),a=>a.files[0].path=a.files[1].path,
    a=>a.files[0].path=a.files[0].path.replace('run-54JQVf','run-OTHER'),
    a=>a.files[0].path=a.files[0].path.replace('Cache_Data','Local Storage'),
    a=>a.files[0].unit+='-other',a=>a.files[0].category='Cookies',a=>a.files[0].path+=':extra',
    a=>a.files[0].bytes++,a=>a.files[0].sha256='bad',a=>a.deleted_directories=1,
    a=>a.existing_acl_writes=1,a=>a.deleted_bytes=0,a=>a.preserved_files.pop(),
    a=>a.preserved_files[0].path=a.files[0].path
  ]){const a=complete();mutate(a);assert.throws(()=>isolatedTestCacheRecords({audits:[a]}));}
  assert.throws(()=>isolatedTestCacheRecords({audits:[complete(),complete()]}));
});
test('entry point has no recursive deletion, process stop/start, installed-profile or network operation',()=>{
  const code=fs.readFileSync(path.join(__dirname,'remove-isolated-test-cache.ps1'),'utf8');
  assert.doesNotMatch(code,/\b(Remove-Item|Stop-Process|Start-Process|Invoke-WebRequest|Invoke-RestMethod|Set-Acl|DeleteEmptyDirectory)\b/);
  assert.ok(code.indexOf('Write-TestCacheIndex $document $audit $index $ExpectedIndexSha256')<code.indexOf('Remove-TestCachePinned $sources'));
});
