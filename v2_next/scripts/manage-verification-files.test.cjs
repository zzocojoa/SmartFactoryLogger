const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const os=require('node:os');
const path=require('node:path');
const {inside,plain,walk,hash,sourceCatalog,desktopEvidenceRoot,assertMigrationStates,assertReviewedCleanupStates,archiveDuplicateRule,releaseRetention,releaseDestinationName,transferBatchSpecs,buildCheckoutClass}=require('./manage-verification-files.cjs');
test('unfinished ACL repair prevents unrelated registry rewrites',()=>{
  assert.doesNotThrow(()=>assertMigrationStates({audits:[{kind:'DESKTOP_DEPENDENCY_ACL_REPAIR',state:'COMPLETE'}]}));
  for(const state of ['APPLYING','PARTIAL_STOPPED',undefined])assert.throws(()=>assertMigrationStates({audits:[{kind:'DESKTOP_DEPENDENCY_ACL_REPAIR',state}]}),/ACL repair incomplete/);
});
test('incomplete reviewed cache deletion blocks inventory and completion verification',()=>{
  assert.doesNotThrow(()=>assertReviewedCleanupStates({audits:[{kind:'DESKTOP_BUILDS_CACHE_REVIEW'}]}));
  assert.doesNotThrow(()=>assertMigrationStates({audits:[{kind:'DESKTOP_BUILDS_CACHE_REVIEW',cleanup:{state:'COMPLETE'}}]}));
  for(const state of ['DELETING','PARTIAL_STOPPED','unknown']){
    const index={audits:[{kind:'DESKTOP_BUILDS_CACHE_REVIEW',cleanup:{state}}]};
    assert.throws(()=>assertReviewedCleanupStates(index),/cleanup incomplete/);
    assert.throws(()=>assertMigrationStates(index),/cleanup incomplete/);
  }
});
test('per-file dependency deletion journals block other management writes until complete',()=>{
  assert.doesNotThrow(()=>assertReviewedCleanupStates({audits:[{kind:'DESKTOP_BUILDS_DEPENDENCY_CLEANUP_PLAN'}]}));
  assert.doesNotThrow(()=>assertReviewedCleanupStates({audits:[{kind:'DESKTOP_BUILDS_DEPENDENCY_CLEANUP_PLAN',cleanup:{state:'COMPLETE'}}]}));
  for(const state of ['DELETING','PARTIAL_STOPPED','unknown'])assert.throws(()=>assertMigrationStates({audits:[{kind:'DESKTOP_BUILDS_DEPENDENCY_CLEANUP_PLAN',cleanup:{state}}]}),/Dependency cleanup incomplete/);
});
test('checkout classification protects tracked source, configuration, Git and unique evidence',()=>{
  assert.equal(buildCheckoutClass('.git/objects/pack/example.pack',false,false),'PROTECT_GIT_METADATA');
  assert.equal(buildCheckoutClass('v2_next/backend/build/handwritten.py',true,true),'PROTECT_GIT_TRACKED_SOURCE');
  assert.equal(buildCheckoutClass('v2_next/node_modules/local-edit.js',false,false),'KEEP_UNTRACKED_REVIEW');
  for(const name of ['v2_next/.env','v2_next/.env.local','v1_legacy/config/config.ini','v2_next/backend/config.ini.bak'])assert.equal(buildCheckoutClass(name,true,false),'PROTECT_CONFIGURATION');
  assert.equal(buildCheckoutClass('v2_next/.tmp_test_appdata/SmartFactoryLogger/logs/data/run.csv',false,true),'KEEP_TEST_EVIDENCE');
  for(const name of ['v2_next/dist/installer.exe','v2_next/backend/dist/bundle.json','v2_next/frontend/dist/index.html'])assert.equal(buildCheckoutClass(name,false,true),'KEEP_BUILD_OUTPUT_REVIEW');
});
test('checkout candidates require exact reviewed prefixes and ignored status',()=>{
  for(const name of ['v2_next/node_modules/a.js','v2_next/frontend/node_modules/b.js','v2_next/backend/.venv/Scripts/python.exe','v2_next/backend/browsers/chrome.exe'])assert.equal(buildCheckoutClass(name,false,true),'CANDIDATE_REINSTALLABLE_DEPENDENCY');
  for(const name of ['v2_next/.mypy_cache/cache.db','v2_next/.ruff_cache/entry','v2_next/backend/tests/__pycache__/a.pyc'])assert.equal(buildCheckoutClass(name,false,true),'CANDIDATE_REGENERABLE_CACHE');
  assert.equal(buildCheckoutClass('v2_next/backend/build/analysis.toc',false,true),'CANDIDATE_REGENERABLE_BUILD_INTERMEDIATE');
  for(const name of ['v2_next/node_modules-other/a.js','v2_next/backend/build-other/a.py','v1_legacy/node_modules/a.js','v2_next/backend/tests/__pycache__/notes.md'])assert.equal(buildCheckoutClass(name,false,true),'KEEP_IGNORED_REVIEW');
  assert.equal(buildCheckoutClass('v2_next\\backend\\build\\a.toc',false,true),'CANDIDATE_REGENERABLE_BUILD_INTERMEDIATE');
});
test('transfer batches bind three exact revision folders without widening the Desktop boundary',()=>{
  const specs=transferBatchSpecs();
  assert.deepEqual(specs.map(s=>s.count),[3,3,6]);
  assert.equal(new Set(specs.map(s=>s.zip_sha256)).size,3);
  assert.deepEqual(specs.map(s=>s.source_leaf),['SmartFactoryLogger_Transfer_0695a0f_20260806','SmartFactoryLogger_Transfer_0695a0f_20260806_R2','SmartFactoryLogger_Transfer_0695a0f_20260806_R3']);
  const runner=fs.readFileSync(path.join(__dirname,'migrate-desktop-test.ps1'),'utf8');
  for(const s of specs){
    assert.match(s.zip_sha256,/^[A-F0-9]{64}$/);
    assert.ok(runner.includes("'"+s.collection+"'{'"+s.source_leaf+"'}"));
    assert.ok(runner.includes("'"+s.collection+"'{'"+s.kind+"'}"));
  }
});
test('only the exact reviewed field-kit parent receives a short archive alias',()=>{
  const parent='spot_connecttimeout_field_kit_077b6b1c_rebuilt_20260727';
  assert.equal(releaseDestinationName(path.join(parent,'nested','a.txt')),path.join('kit-077b6b1','nested','a.txt'));
  assert.equal(releaseDestinationName(path.join(parent+'-other','a.txt')),path.join(parent+'-other','a.txt'));
  assert.equal(releaseDestinationName(''), '');
});
test('release retention preserves published sets and maps exact same-name staging duplicates directly',()=>{
  const f=(name,sha256='A',bytes=10)=>({name:path.normalize(name),source:path.resolve('release-fixture',name),sha256,bytes});
  const releaseA=f('release_a/lib.dll'),releaseB=f('release_b/lib.dll'),staged=f('staging/lib.dll');
  const loose=f('lib.dll'),different=f('staging/other.dll'),changed=f('changed/lib.dll','B');
  const short=f('a/proof.bin'),long=f('long/tree/proof.bin');
  const files=[long,short,staged,releaseB,releaseA,loose,different,changed];
  const keep=releaseRetention(files);
  for(const entry of [releaseA,releaseB,loose,different,changed,short])assert.equal(keep.get(entry.source),entry);
  assert.equal(keep.get(staged.source),loose);
  assert.equal(keep.get(long.source),short);
  for(const entry of files)assert.equal(keep.get(keep.get(entry.source).source),keep.get(entry.source),'no duplicate chains');
});
test('partial migrations of any collection cannot be overwritten by a scan',()=>{
  assert.doesNotThrow(()=>assertMigrationStates({migrations:[{state:'PLANNED'},{state:'COMPLETE'}]}));
  for(const state of ['COPYING','COPIED_VERIFIED','REMOVING_SOURCES','PARTIAL_STOPPED','unknown'])assert.throws(()=>assertMigrationStates({migrations:[{kind:'DESKTOP_SMARTFACTORY_MIGRATION',state}]}),/incomplete/);
});
test('archive dedup rules select only reviewed extraction members',()=>{
  assert.equal(archiveDuplicateRule('spot-temperature-v25-qa-extracted-20260728/README.md').entry,'README.md');
  assert.equal(archiveDuplicateRule('pr171-windows-145/nsis-inspect/contents/resources/backend/SmartFactoryBackend.exe').entry,'SmartFactory_Portable\\SmartFactoryBackend.exe');
  for(const name of ['README.md','spot-temperature-v25-qa-extracted-20260728/../README.md','spot-temperature-v25-qa-extracted-20260728/unknown.txt','pr171-windows-145/nsis-inspect/$PLUGINSDIR/app-64.7z'])assert.equal(archiveDuplicateRule(name),null);
});
test('boundary requires a child separator, not a prefix lookalike',()=>{
  const root=path.resolve('fixture');
  assert.equal(inside(root,root),false);
  assert.equal(inside(root+'-other',root),false);
  assert.equal(inside(path.join(root,'child'),root),true);
});
test('source catalog anchors still exist in the current source',()=>{
  const catalog=sourceCatalog();assert.equal(catalog.length,20);
  assert.ok(catalog.every(row=>row.line>0));
  assert.ok(catalog.some(row=>row.kind==='protected_runtime'));
});
test('receipt location changes only after the exact migration is complete',()=>{
  const a=path.resolve('legacy'),b=path.resolve('new-evidence');
  const entry={kind:'DESKTOP_TEST_MIGRATION',source:a,destination:b,state:'PLANNED'};
  assert.equal(desktopEvidenceRoot({},a,b),a);
  assert.equal(desktopEvidenceRoot({migrations:[entry]},a,b),a);
  assert.equal(desktopEvidenceRoot({migrations:[{...entry,state:'COMPLETE'}]},a,b),b);
  for(const state of ['COPYING','COPIED_VERIFIED','REMOVING_SOURCES','PARTIAL_STOPPED'])assert.throws(()=>desktopEvidenceRoot({migrations:[{...entry,state}]},a,b),/incomplete/);
  assert.throws(()=>desktopEvidenceRoot({migrations:[entry,entry]},a,b),/Ambiguous/);
  assert.throws(()=>desktopEvidenceRoot({migrations:[{...entry,destination:path.resolve('elsewhere')}]},a,b),/Unexpected/);
});
test('inventory does not follow a junction or nested checkout; hashes ordinary bytes',async()=>{
  const root=fs.mkdtempSync(path.join(os.tmpdir(),'sfl-verification-manager-test-'));
  const child=path.join(root,'child'),linked=path.join(root,'link'),checkout=path.join(root,'checkout');
  fs.mkdirSync(child);fs.mkdirSync(checkout);
  fs.writeFileSync(path.join(child,'a.txt'),'abc');
  fs.writeFileSync(path.join(checkout,'.git'),'synthetic marker');
  fs.symlinkSync(child,linked,'junction');
  try {
    const result=walk(root);
    assert.equal(result.files.length,1);
    assert.equal(result.links.length,1);
    assert.equal(result.errors[0].code,'SOURCE_CHECKOUT_EXCLUDED');
    assert.throws(()=>plain(path.join(linked,'a.txt')),/Link boundary/);
    assert.equal(await hash(path.join(child,'a.txt')),'BA7816BF8F01CFEA414140DE5DAE2223B00361A396177A9CB410FF61F20015AD');
  }finally{
    // Only exact fixture leaves; no recursive delete and never follow the link.
    fs.unlinkSync(linked);fs.unlinkSync(path.join(child,'a.txt'));fs.unlinkSync(path.join(checkout,'.git'));
    fs.rmdirSync(child);fs.rmdirSync(checkout);fs.rmdirSync(root);
  }
});
