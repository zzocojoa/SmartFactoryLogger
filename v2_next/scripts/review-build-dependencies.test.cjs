const test=require('node:test');
const assert=require('node:assert/strict');
const path=require('node:path');
const {parseRecord,recordPath,platformExcluded,compareNode,gridPatchState}=require('./review-build-dependencies.cjs');
test('RECORD CSV accepts escaped quotes, quoted commas, CRLF and empty hash fields',()=>{
  assert.deepEqual(parseRecord('"a,b",sha256=abc,3\r\n"a""b",,\r\nlast,,0'),[['a,b','sha256=abc','3'],['a"b','',''],['last','','0']]);
  assert.deepEqual(parseRecord('a,,\n'),[['a','','']]);
  for(const text of ['"unclosed,,','a,b','a,b,c,d','"a"oops,b,c','a"b,,'])assert.throws(()=>parseRecord(text));
});
test('RECORD permits Scripts references within venv but rejects escapes and drive paths',()=>{
  const root=path.resolve('fixture-venv'),site=path.join(root,'Lib/site-packages');
  assert.equal(recordPath(root,site,'../../Scripts/pip.exe'),path.join(root,'Scripts/pip.exe'));
  for(const name of ['../../../outside','/absolute','C:/absolute','a\\b','a\0b',''])assert.throws(()=>recordPath(root,site,name));
});
test('only optional packages excluded by this platform/CPU are acceptable omissions',()=>{
  assert.equal(platformExcluded({os:['win32'],cpu:['x64']},'win32','x64'),false);
  assert.equal(platformExcluded({os:['!win32']},'win32','x64'),true);
  assert.equal(platformExcluded({os:['win32'],cpu:['arm64']},'win32','x64'),true);
  const lock={packages:{'':{},'node_modules/a':{version:'1',integrity:'sha512-a'},'node_modules/b':{version:'1',integrity:'sha512-b',optional:true,os:['darwin']},'node_modules/c':{version:'1',integrity:'sha512-c',optional:true,os:['win32']}}};
  const hidden={packages:{'node_modules/a':lock.packages['node_modules/a']}};
  const result=compareNode(lock,hidden,{'node_modules/a':{version:'1'}});
  assert.equal(result.matching_versions,1);assert.deepEqual(result.absent_optional_other_platform,['node_modules/b']);
  assert.deepEqual(result.problems,[{path:'node_modules/c',reason:'MISSING_REQUIRED_OR_CURRENT_PLATFORM_PACKAGE'}]);
});
test('Node checks detect version/integrity/hidden-lock gaps without persisting resolved URLs',()=>{
  const lock={packages:{'':{},'node_modules/a':{version:'1',integrity:'sha512-a',resolved:'SECRET_URL'}}};
  const hidden={packages:{'node_modules/a':{version:'2',integrity:'sha512-b'},'node_modules/extra':{version:'1'}}};
  const result=compareNode(lock,hidden,{'node_modules/a':{version:'2'}});
  assert.ok(result.problems.some(p=>p.reason==='INSTALLED_VERSION_DIFFERS'));
  assert.ok(result.problems.some(p=>p.reason==='HIDDEN_LOCK_PACKAGE_MISSING'));
  assert.ok(!JSON.stringify(result).includes('SECRET_URL'));
  assert.ok(compareNode(lock,{packages:{}},{'node_modules/a':{version:'1'}}).problems.some(p=>p.reason==='HIDDEN_LOCK_ENTRY_MISSING'));
});
test('all three Grafana constants must match the intentional postinstall patch',()=>{
  const text='const GRID_CELL_HEIGHT = 20;\nconst GRID_CELL_VMARGIN = 4;\nconst GRID_COLUMN_COUNT = 60;';
  assert.ok(gridPatchState(text).every(v=>v.matches));
  assert.ok(gridPatchState(text+'\nconst GRID_COLUMN_COUNT = 24;').some(v=>!v.matches));
  assert.ok(gridPatchState('').every(v=>!v.matches));
});
