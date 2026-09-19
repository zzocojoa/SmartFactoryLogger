const test=require('node:test'),assert=require('node:assert/strict'),path=require('node:path');
const {assertRunRoot,childEnvironment,assertNoRunningPhase,generatedDifference,launcherIdentity}=require('./rehearse-build-dependencies.cjs');
test('reinstall accepts only a single new run under the repository temporary boundary',()=>{
  const id='428c970f-1f0e-4127-802c-7b4ba9d621c0',root=path.resolve(__dirname,'../.tmp','dep-'+id);
  assert.equal(assertRunRoot(root,id),root);
  for(const wrong of [path.dirname(root),root+'-extra',path.resolve(root,'..','elsewhere')])assert.throws(()=>assertRunRoot(wrong,id));
  assert.throws(()=>assertRunRoot(root,'../source'));
});
test('child tools receive explicit temporary caches and no inherited secrets or proxy configuration',()=>{
  const root=path.resolve('synthetic-run'),env=childEnvironment(root);
  for(const key of ['PIP_INDEX_URL','NPM_TOKEN','GITHUB_TOKEN','HTTP_PROXY','HTTPS_PROXY','NODE_OPTIONS','PYTHONPATH','ELECTRON_MIRROR'])assert.equal(env[key],undefined);
  assert.equal(env.PIP_CONFIG_FILE,'NUL');assert.equal(env.npm_config_cache,path.join(root,'npm-cache'));assert.equal(env.PLAYWRIGHT_BROWSERS_PATH,path.join(root,'browsers'));
  assert.equal(env.TEMP,path.join(root,'temp'));
});
test('a running or interrupted phase prevents another registry writer from starting',()=>{
  assert.throws(()=>assertNoRunningPhase({phases:{frontend:{state:'RUNNING'}}}),/Another phase/);
  assert.throws(()=>assertNoRunningPhase({state:'COMPARING',phases:{frontend:{state:'PASS'}}}),/Another phase/);
  assert.doesNotThrow(()=>assertNoRunningPhase({phases:{frontend:{state:'PACKAGES_INSTALLED_SCRIPTS_PENDING'},python:{state:'PASS'}}}));
});
test('only narrowly named generated files are excluded from exact byte reproducibility',()=>{
  assert.equal(generatedDifference('node','.package-lock.json'),'NPM_INSTALL_METADATA');
  assert.equal(generatedDifference('browsers','.links/a1b2c3'),'PLAYWRIGHT_INSTALL_PATH_LINK');
  assert.equal(generatedDifference('python','Lib/site-packages/pip-24.2.dist-info/RECORD'),'PIP_INSTALL_METADATA');
  assert.equal(generatedDifference('python','Scripts/pip.exe'),'PYTHON_ENTRYPOINT_LAUNCHER_PATH');
  for(const [group,name] of [['node','package/index.js'],['python','Scripts/python.exe'],['python','Lib/site-packages/module.py'],['python','Lib/site-packages/module.pyd'],['browsers','chromium-1228/chrome-win64/chrome.exe']])assert.equal(generatedDifference(group,name),null);
});
test('Python launcher comparison requires the same stub and embedded entrypoint, not just an exe name',()=>{
  const make=(venv,main,stub='MZ-stub',separator='')=>{
    const member=Buffer.from('__main__.py'),payload=Buffer.from(main),header=Buffer.alloc(30),end=Buffer.alloc(22);
    header.writeUInt32LE(0x04034b50);header.writeUInt32LE(payload.length,18);header.writeUInt16LE(member.length,26);
    end.writeUInt32LE(0x06054b50);end.writeUInt16LE(1,10);
    return Buffer.concat([Buffer.from(stub+'#!'+path.join(venv,'Scripts/python.exe')+'\n'+separator),header,member,payload,end]);
  };
  const a=path.resolve('venv-a'),b=path.resolve('venv-b');
  const left=launcherIdentity(make(a,'print(1)'),a),right=launcherIdentity(make(b,'print(1)'),b);
  assert.deepEqual(left,right);
  assert.notDeepEqual(left,launcherIdentity(make(b,'print(2)'),b));
  assert.notDeepEqual(left,launcherIdentity(make(b,'print(1)','MZ-other'),b));
  assert.equal(launcherIdentity(Buffer.from('not a launcher'),a),null);
  assert.equal(launcherIdentity(make(a,'print(1)'),b),null);
  assert.deepEqual(launcherIdentity(make(a,'print(1)','MZ-stub#!not-a-shebang'),a),launcherIdentity(make(b,'print(1)','MZ-stub#!not-a-shebang'),b));
  const crlfA=launcherIdentity(make(a,'print(1)','MZ-stub','\r\n'),a),crlfB=launcherIdentity(make(b,'print(1)','MZ-stub','\r\n'),b);
  assert.ok(crlfA);assert.deepEqual(crlfA,crlfB);
});
