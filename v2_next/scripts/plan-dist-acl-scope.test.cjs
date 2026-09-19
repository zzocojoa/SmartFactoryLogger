'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {proposal,aclCode,reviewId}=require('./plan-dist-acl-scope.cjs');
const {specs}=require('./plan-dist-cleanup.cjs');
const root=path.resolve(__dirname,'../dist');
function fixture(){return {id:reviewId,files:specs.map(s=>({path:path.join(root,s.relative),bytes:10,sha256:'A'.repeat(64)})),retained_ci_sets:[...new Set(specs.map(s=>s.keeper.split('/')[0]))].map(n=>({root:path.join(root,n),files:['SHA256SUMS.txt','installer.exe','portable.zip'].map(p=>({path:path.join(root,n,p),bytes:20,sha256:'B'.repeat(64)}))}))};}
test('proposal keeps existing ACLs unchanged and treats migration as new authority',()=>{
  const p=proposal(fixture());assert.deepEqual(p.existing_acl_changes,[]);assert.deepEqual(p.existing_owner_group_changes,[]);
  for(const k of ['migration_authorized','acl_change_authorized','deletion_authorized','execution_ready'])assert.equal(p[k],false);
  assert.equal(p.copy_files,12);assert.equal(p.new_directories.length,8);assert.equal(p.eventual_original_ci_removal_files.length,12);assert.equal(p.existing_duplicate_proposal.length,9);
  assert.equal(new Set(p.groups.map(g=>g.destination)).size,4);assert.ok(p.max_destination_path_chars<=240);
});
test('space accounting distinguishes copy-only growth from fully verified migration savings',()=>{
  const p=proposal(fixture());assert.equal(p.copy_bytes,240);assert.equal(p.copy_only_net_logical_bytes_freed,-240);
  assert.equal(p.copy_then_only_nine_duplicates_net_logical_bytes_freed,-150);assert.equal(p.complete_migration_and_nine_duplicates_net_logical_bytes_freed,90);
});
test('changed identity or incomplete/duplicate CI membership is rejected',()=>{
  for(const mutate of [r=>r.id='other',r=>r.files.pop(),r=>r.retained_ci_sets.pop(),r=>r.retained_ci_sets[0].files.pop(),r=>r.retained_ci_sets[0].files[1].path=r.retained_ci_sets[0].files[0].path,r=>r.retained_ci_sets[0].files[0].path=path.resolve('outside.txt')]){
    const r=fixture();mutate(r);assert.throws(()=>proposal(r));
  }
});
test('read helper has no mutations; registry publication is exclusive and hash-bound',()=>{
  const code=fs.readFileSync(path.join(__dirname,'plan-dist-acl-scope.cjs'),'utf8');
  assert.doesNotMatch(aclCode,/(?:Remove-Item|Set-Acl|New-Item|Start-Process|Stop-Process|Invoke-WebRequest|Invoke-RestMethod)\b/i);
  assert.doesNotMatch(code,/fs\.(?:rm|unlink|rmdir|chmod|chown|copyFile|mkdir)(?:Sync)?\(/);
  assert.match(code,/prior_hold_resolved:false/);assert.match(code,/fs\.openSync\(registry\+'\.writing','wx'\)/);
  assert.match(code,/index\.audits\.some\(a=>a\.kind===kind\)/);
});
