const test=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),crypto=require('node:crypto');
const {child,targets,inTarget,stable,readFingerprint,assertReinstallComplete}=require('./plan-dependency-cleanup.cjs');

test('canonical child paths reject escapes, absolute paths, streams and mixed separators',()=>{
  const root=path.resolve('synthetic-plan-root');
  assert.equal(child(root,'a/b.txt'),path.join(root,'a','b.txt'));
  for(const value of ['',null,'/a','../a','a/../b','a/./b','a//b','a/','a\\b','C:/a','a:stream','a\0b'])assert.throws(()=>child(root,value));
});

test('exactly eight dependency targets exclude the retained recovery material',()=>{
  const checkout=path.resolve('old-checkout'),run=path.resolve('reinstall'),roots=targets(checkout,run);
  assert.equal(roots.length,8);assert.equal(new Set(roots.map(r=>r.root.toLowerCase())).size,8);
  assert.deepEqual(roots.map(r=>r.id),['old-node','old-frontend','old-python','old-browsers','test-node','test-frontend','test-python','test-node-cache']);
  for(const root of roots){assert.ok(inTarget(path.join(root.root,'file'),roots));assert.ok(!inTarget(root.root+'-other/file',roots));}
  for(const value of ['browsers/chrome.exe','wheels/a.whl','npm-cache/archive','electron-cache/electron.zip','logs/install.log','node/package-lock.json','frontend/package.json','python-hashed.txt'])assert.ok(!inTarget(child(run,value),roots));
  for(const value of ['.git/config','v2_next/backend/config.ini','v2_next/package-lock.json','v2_next/backend/dist/backend.exe'])assert.ok(!inTarget(child(checkout,value),roots));
});

test('file identity must retain size, timestamps, inode and device',()=>{
  const a={size:3n,mtimeNs:10n,ctimeNs:20n,ino:30n,dev:40n};
  assert.ok(stable(a,{...a}));
  for(const key of Object.keys(a))assert.ok(!stable(a,{...a,[key]:a[key]+1n}));
});

test('fingerprints preserve exact timestamp strings and detect file content',()=>{
  const root=fs.mkdtempSync(path.join(os.tmpdir(),'sfl-dependency-plan-test-')),file=path.join(root,'fixture.txt');
  try{
    fs.writeFileSync(file,'abc',{flag:'wx'});
    const actual=readFingerprint(file),stat=fs.statSync(file,{bigint:true});
    assert.equal(actual.sha256,crypto.createHash('sha256').update('abc').digest('hex').toUpperCase());
    assert.equal(actual.bytes,3);assert.equal(actual.mtime_ns,stat.mtimeNs.toString());assert.equal(actual.ctime_ns,stat.ctimeNs.toString());
    assert.equal(actual.birthtime_ns,stat.birthtimeNs.toString());assert.doesNotThrow(()=>JSON.stringify(actual));
    assert.throws(()=>readFingerprint(root),/Non-file/);
  }finally{if(fs.existsSync(file))fs.unlinkSync(file);fs.rmdirSync(root);}
});

test('fingerprint refuses a junction without reading its destination',()=>{
  const root=fs.mkdtempSync(path.join(os.tmpdir(),'sfl-dependency-link-test-')),link=path.join(root,'junction'),target=path.join(root,'target');
  try{fs.mkdirSync(target);fs.symlinkSync(target,link,'junction');assert.throws(()=>readFingerprint(link),/Non-file/);}
  finally{if(fs.existsSync(link))fs.unlinkSync(link);if(fs.existsSync(target))fs.rmdirSync(target);fs.rmdirSync(root);}
});

test('package installation alone cannot substitute for successful hooks and browser recovery',()=>{
  const ready={gap_review:{result:'REINSTALL_VERIFIED_WITH_GENERATED_DIFFERENCES_AND_PRESERVED_TEST_EVIDENCE'},phases:{node:{state:'PACKAGES_INSTALLED_SCRIPTS_PENDING'},frontend:{state:'PACKAGES_INSTALLED_SCRIPTS_PENDING'},python:{state:'PASS'},'node-scripts':{state:'PASS'},'frontend-scripts':{state:'PASS'},browsers:{state:'PASS'}}};
  assert.doesNotThrow(()=>assertReinstallComplete(ready));
  for(const key of Object.keys(ready.phases)){
    const missing=structuredClone(ready);delete missing.phases[key];assert.throws(()=>assertReinstallComplete(missing));
    const failed=structuredClone(ready);failed.phases[key].state='FAIL';assert.throws(()=>assertReinstallComplete(failed));
  }
  const pending=structuredClone(ready);pending.phases['node-scripts'].state='PACKAGES_INSTALLED_SCRIPTS_PENDING';assert.throws(()=>assertReinstallComplete(pending));
  const gaps=structuredClone(ready);gaps.gap_review.result='UNRESOLVED';assert.throws(()=>assertReinstallComplete(gaps));
});
