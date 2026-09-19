'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {specs,child,choose,preserveReason,parseSums,metadataCode,metadataHolds}=require('./plan-dist-cleanup.cjs');
const root=path.resolve(__dirname,'../dist');
const records=()=>specs.map(s=>({relative:s.relative,path:child(root,s.relative),bytes:7,sha256:'A'.repeat(64),decision:'CANDIDATE_EXACT_DUPLICATE_REQUIRES_REFERENCE_REVIEW',retained_copy:{path:child(root,s.keeper),bytes:7,sha256:'A'.repeat(64)}}));
test('proposal is exactly nine root files, all with CI keepers; no kit/build/QA trees',()=>{
  assert.equal(specs.length,9);assert.equal(new Set(specs.map(s=>s.relative.toLowerCase())).size,9);
  for(const s of specs){assert.doesNotMatch(s.relative,/[\\/]/);assert.match(s.keeper,/^ci-[^/]+\//);}
  assert.equal(specs.filter(s=>s.relative.endsWith('.exe')).length,5);
  assert.equal(specs.filter(s=>s.relative.endsWith('.txt')).length,4);
  assert.equal(choose(records()).length,9);
});
test('path resolution rejects escape, ADS, alternate separator and empty segments',()=>{
  for(const value of ['../escape','a/../b','a\\b','C:/file','/file','a//b','x:ads','a/./b',''])assert.throws(()=>child(root,value));
});
test('mapping requires exact classified path, keeper, bytes and hash',()=>{
  for(const mutate of [r=>r.pop(),r=>r[0].retained_copy.sha256='B'.repeat(64),r=>r[0].retained_copy.bytes++,r=>r[0].retained_copy.path=r[1].path,r=>r[0].path=path.join(root,'elsewhere'),r=>r[0].decision='KEEP']){
    const r=records();mutate(r);assert.throws(()=>choose(r));
  }
});
test('keep reasons do not treat same-byte recovery/kit members as disposable',()=>{
  assert.match(preserveReason('spot-tcp-canary-bfd9be7/collector.ps1'),/PSSCRIPTROOT/);
  assert.match(preserveReason('spot-temperature-v25-qa.zip.sha256.txt'),/SIDECAR/);
  assert.match(preserveReason('canary_field_kit_inspection_20260807/manifest.json'),/WHOLE/);
  assert.match(preserveReason('v1018_33058fc_smoke_recovery_R2/dependencies/a.exe'),/TOGETHER/);
});
test('CI manifests accept standard text/binary separators and reject path traversal or duplicate members',()=>{
  const h='a'.repeat(64);assert.deepEqual(parseSums(`${h}  Installer.exe\r\n${h} *Portable.zip\r\n`),[{name:'Installer.exe',sha256:h.toUpperCase()},{name:'Portable.zip',sha256:h.toUpperCase()}]);
  for(const name of ['../a.exe','a/b','a\\b','x:ads','..'])assert.throws(()=>parseSums(`${h}  ${name}`));
  assert.throws(()=>parseSums(`${h}  a.exe\n${h}  A.exe`));assert.throws(()=>parseSums('bad manifest'));
});
test('metadata holds on alternate streams, read-only targets, or untrusted ownership/writes',()=>{
  const ok={path:'fixed',exclusive_read_pass:true,owner_trusted:true,parent_owner_trusted:true,outside_writer_sids:[],named_stream_count:0,attributes:32};
  assert.deepEqual(metadataHolds([ok]),[]);
  for(const patch of [{exclusive_read_pass:false},{owner_trusted:false},{parent_owner_trusted:false},{outside_writer_sids:['unknown']},{named_stream_count:1},{attributes:33}]){
    const holds=metadataHolds([{...ok,...patch}]);assert.equal(holds.length,1);assert.equal(holds[0].path,'fixed');assert.equal(holds[0].reasons.length,1);
  }
});
test('proposal has no destructive/product/ACL/network execution and cannot authorize deletion',()=>{
  const code=fs.readFileSync(path.join(__dirname,'plan-dist-cleanup.cjs'),'utf8');
  assert.doesNotMatch(code,/fs\.(?:rm|unlink|rmdir|chmod|chown|copyFile|mkdir)(?:Sync)?\(/);
  assert.doesNotMatch(metadataCode,/(?:Remove-Item|Stop-Process|Start-Process|Set-Acl|Invoke-WebRequest|Invoke-RestMethod)\b/i);
  assert.match(code,/deletion_authorized:false,deletion_ready:false/);
  assert.match(code,/fs\.openSync\(registry\+'\.writing','wx'\)/);
  assert.match(code,/holds.length\?'PLAN_REVIEW_HOLD':'PLAN_COMPLETE_AWAITING_APPROVAL'/);
  assert.match(code,/if\(staticInfo.review_digest!==reviewedReferenceDigest\|\|staticInfo.skipped.length\)throw/);
  assert.match(metadataCode,/\[IO.File\]::Open\(\$r.path,'Open','Read','None'\)/);
});
