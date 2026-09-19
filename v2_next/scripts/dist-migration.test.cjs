'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),path=require('node:path');
const {contract}=require('./prepare-dist-migration.cjs');
const {assertReviewedCleanupStates,distArchiveRecords}=require('./manage-verification-files.cjs');
const {specs}=require('./plan-dist-cleanup.cjs');
const {reviewId}=require('./plan-dist-acl-scope.cjs');

// Synthetic bytes/hashes only. The fixed counts and names are the contract,
// not a dependency on a private operator registry or retained release payloads.
function fixture() {
  const root=path.resolve(__dirname,'../dist');
  const groupNames=[...new Set(specs.map(s=>s.keeper.split('/')[0]))];
  const groups=groupNames.map((name,i)=>{
    const names=[...new Set(specs.filter(s=>s.keeper.startsWith(name+'/')).map(s=>path.basename(s.keeper)))];
    assert.equal(names.length,2);
    return {root:path.join(root,name),files:[...names,'portable.zip'].map((n,j)=>({
      path:path.join(root,name,n),bytes:j===0?10:j===1?148848857+(i===0?1:0):382886413+(i===0?3:0),sha256:'A'.repeat(64)
    }))};
  });
  const kept=new Map(groups.flatMap(g=>g.files).map(f=>[f.path,f]));
  const files=specs.map(s=>{
    const witness=kept.get(path.join(root,...s.keeper.split('/')));
    return {...witness,path:path.join(root,s.relative),retained_copy:{...witness}};
  });
  // Five installer duplicates plus four manifest duplicates: 744244326 bytes.
  // Four kept sets: 2126941124 bytes. Values are synthetic, not file contents.
  assert.equal(files.reduce((n,f)=>n+f.bytes,0),744244326);
  assert.equal(groups.flatMap(g=>g.files).reduce((n,f)=>n+f.bytes,0),2126941124);
  return {audits:[{id:reviewId,state:'PLAN_REVIEW_HOLD',root,files,retained_ci_sets:groups},
    {id:'4cfa13f4-2b5c-443f-ae7b-44da3918dcc5',state:'SCOPE_REVIEW_COMPLETE_ALTERNATIVE_NEEDS_DECISION',
      metadata:[...files,...groups.flatMap(g=>g.files)].map(f=>({path:f.path,bytes:f.bytes,sha256:f.sha256})),acl_boundaries:[]}]};
}
test('pending/partial archive transactions block manager scan/verify',()=>{
  for(const state of ['PREPARED','COPYING','DELETING','PARTIAL_STOPPED'])assert.throws(()=>assertReviewedCleanupStates({audits:[{kind:'DESKTOP_DIST_PROTECTED_CI_MIGRATION',state}]}),/Dist migration/);
});
test('empty archive mappings preserve existing compatibility',()=>assert.deepEqual(distArchiveRecords({audits:[]}),[]));
test('malformed completed transaction is rejected',()=>assert.throws(()=>distArchiveRecords({audits:[{kind:'DESKTOP_DIST_PROTECTED_CI_MIGRATION',state:'COMPLETE',plan:{archive_root:'C:\\wrong',groups:[],files:[]}}]})));
test('synthetic contract retains 12 files and removes exactly 21, without directory deletion',()=>{
  const x=fixture();
  const p=contract(x);
  assert.equal(p.files.length,21);assert.equal(p.groups.flatMap(g=>g.files).length,12);
  assert.equal(p.files.filter(f=>f.action==='REMOVE_DUPLICATE').length,9);
  assert.equal(p.net_logical_bytes_freed,744244326);assert.equal(p.new_directories.length,8);
  assert.ok(p.files.every(f=>f.keeper.startsWith(p.archive_root+'\\')));
  const bad=structuredClone(x);bad.audits.find(a=>a.id==='45788395-d10c-4a97-a04c-1049f635942c').files[0].retained_copy.path='C:\\outside';
  assert.throws(()=>contract(bad),/mapping/);
});
