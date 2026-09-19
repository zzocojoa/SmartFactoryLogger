// Isolated development dependency reinstall. No product launch, source deletion or server access.
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),crypto=require('node:crypto');
const {spawn,execFileSync}=require('node:child_process');
const {inflateRawSync}=require('node:zlib');
const {plain,walk,hash,assertMigrationStates}=require('./manage-verification-files.cjs');
const {compareNode}=require('./review-build-dependencies.cjs');
const repo=path.resolve(__dirname,'..'),registry=path.join(repo,'verification-files.local.json');
const reviewId='66e5ce78-5009-400a-a58e-9e5ed2f0a769';
const nodeExe='C:\\Program Files\\nodejs\\node.exe',npmCli='C:\\Program Files\\nodejs\\node_modules\\npm\\bin\\npm-cli.js',basePython='C:\\Python312\\python.exe';
const digest=data=>crypto.createHash('sha256').update(data).digest('hex').toUpperCase();
function assertRunRoot(root,id){
  if(!/^[a-f0-9-]{36}$/.test(id)||root!==path.join(repo,'.tmp','dep-'+id))throw new Error('Invalid rehearsal boundary');
  return root;
}
function load(){plain(registry);const bytes=fs.readFileSync(registry);return {index:JSON.parse(bytes),sha:digest(bytes)};}
function save(loaded){
  if(digest(fs.readFileSync(registry))!==loaded.sha)throw new Error('Concurrent registry update');
  const fd=fs.openSync(registry+'.writing','wx');
  try{fs.writeFileSync(fd,JSON.stringify(loaded.index));fs.fsyncSync(fd);}finally{fs.closeSync(fd);}
  fs.renameSync(registry+'.writing',registry);loaded.sha=digest(fs.readFileSync(registry));
}
function fresh(file,data){plain(path.dirname(file));fs.writeFileSync(file,data,{flag:'wx'});}
function childEnvironment(root){
  const env={};
  for(const key of ['SystemRoot','WINDIR','ComSpec','PATHEXT','PROCESSOR_ARCHITECTURE','NUMBER_OF_PROCESSORS'])if(process.env[key])env[key]=process.env[key];
  return {...env,PATH:[path.dirname(nodeExe),path.dirname(basePython),path.join(process.env.SystemRoot,'System32')].join(';'),TEMP:path.join(root,'temp'),TMP:path.join(root,'temp'),APPDATA:path.join(root,'profile','roaming'),LOCALAPPDATA:path.join(root,'profile','local'),PIP_CONFIG_FILE:'NUL',PIP_DISABLE_PIP_VERSION_CHECK:'1',PYTHONDONTWRITEBYTECODE:'1',PYTHONNOUSERSITE:'1',npm_config_userconfig:path.join(root,'empty-user.npmrc'),npm_config_globalconfig:path.join(root,'empty-global.npmrc'),npm_config_cache:path.join(root,'npm-cache'),npm_config_registry:'https://registry.npmjs.org/',npm_config_audit:'false',npm_config_fund:'false',electron_config_cache:path.join(root,'electron-cache'),PLAYWRIGHT_BROWSERS_PATH:path.join(root,'browsers'),PLAYWRIGHT_SKIP_BROWSER_GC:'1',CI:'1'};
}
function assertNoRunningPhase(run){if(run.state==='COMPARING'||Object.values(run.phases).some(p=>p.state==='RUNNING'))throw new Error('Another phase is running or requires reconciliation');}
async function command(run,label,exe,args,cwd){
  plain(cwd);plain(exe);
  const file=path.join(run.root,'logs',label+'.log'),fd=fs.openSync(file,'wx');
  const entry={label,executable:exe,args,cwd,log:file,state:'RUNNING',started_at:new Date().toISOString()};run.commands.push(entry);
  console.log('[RUN] '+label);
  const result=await new Promise(resolve=>{
    const p=spawn(exe,args,{cwd,env:childEnvironment(run.root),windowsHide:true,stdio:['ignore',fd,fd]});
    p.once('error',error=>resolve({code:null,error:error.code||'SPAWN_ERROR'}));
    p.once('close',(code,signal)=>resolve({code,signal}));
  });
  fs.closeSync(fd);entry.finished_at=new Date().toISOString();entry.exit_code=result.code;entry.state=result.code===0?'PASS':'FAILED';entry.log_sha256=await hash(file);
  console.log('['+entry.state+'] '+label);
  if(result.code!==0)throw new Error('Command failed: '+label+'; inspect managed log');
  return file;
}
async function copyAnchor(review,from,to){
  const relative=path.relative(review.checkout,from).split(path.sep).join('/');
  const pin=review.read_file_hashes.find(a=>a.relative===relative);
  if(!pin||await hash(from)!==pin.sha256)throw new Error('Reviewed input changed');
  const bytes=fs.readFileSync(from);if(digest(bytes)!==pin.sha256)throw new Error('Input changed during read');fresh(to,bytes);
}
async function prepare(){
  const loaded=load(),index=loaded.index,review=index.audits.find(a=>a.id===reviewId);
  if(os.hostname()!=='DESKTOP-SS5CURC'||index.host!==os.hostname()||index.workspace!==repo||!review)throw new Error('Development review identity mismatch');
  assertMigrationStates(index);
  if(index.audits.some(a=>a.kind==='DESKTOP_BUILDS_DEPENDENCY_REINSTALL'&&!['COMPLETE','COMPLETE_WITH_GAPS','STOPPED'].includes(a.state)))throw new Error('Unfinished rehearsal exists');
  const id=crypto.randomUUID(),root=assertRunRoot(path.join(repo,'.tmp','dep-'+id),id);
  plain(path.dirname(root));if(fs.existsSync(root))throw new Error('Rehearsal already exists');
  const run={id,kind:'DESKTOP_BUILDS_DEPENDENCY_REINSTALL',review_id:reviewId,at:new Date().toISOString(),root,checkout:review.checkout,state:'PREPARING',phases:{},commands:[],source_deletions:0,source_writes:0,server_operations:0,authority:'User approved isolated same-version reinstall verification; no original dependency deletion.'};
  index.audits.push(run);index.history.push({at:run.at,kind:run.kind,audit_id:id,state:run.state});save(loaded);
  try{
    fs.mkdirSync(root);
    for(const dir of ['node','frontend','frontend/scripts','temp','logs','wheels','profile','profile/roaming','profile/local'])fs.mkdirSync(path.join(root,dir));
    fresh(path.join(root,'empty-user.npmrc'),'');fresh(path.join(root,'empty-global.npmrc'),'');
    const project=path.join(review.checkout,'v2_next');
    for(const [source,target] of [['','node'],['frontend','frontend']])for(const name of ['package.json','package-lock.json'])await copyAnchor(review,path.join(project,source,name),path.join(root,target,name));
    await copyAnchor(review,path.join(project,'frontend/scripts/patch_grafana_scenes_grid.js'),path.join(root,'frontend/scripts/patch_grafana_scenes_grid.js'));
    const versions=review.python.distributions.map(d=>{if(!/^[A-Za-z0-9_.-]+$/.test(d.name)||!/^\d[\w.+-]*$/.test(d.version))throw new Error('Invalid Python requirement');return d.name+'=='+d.version;});
    fresh(path.join(root,'python-exact.txt'),versions.join('\n')+'\n');
    run.inputs=[];
    for(const f of walk(root).files)run.inputs.push({path:f.path,sha256:await hash(f.path)});
    run.state='PREPARED';save(loaded);console.log(JSON.stringify({id,root,state:run.state}));
  }catch(e){run.state='STOPPED';run.error=e.message;save(loaded);throw e;}
}
async function verifyNode(run,review,group){
  const dir=path.join(run.root,group),lock=JSON.parse(fs.readFileSync(path.join(dir,'package-lock.json'))),hidden=JSON.parse(fs.readFileSync(path.join(dir,'node_modules/.package-lock.json'))),installed={};
  for(const key of Object.keys(lock.packages)){if(!key)continue;const file=path.join(dir,key,'package.json');if(fs.existsSync(file))installed[key]=JSON.parse(fs.readFileSync(file));}
  const result=compareNode(lock,hidden,installed);if(result.problems.length)throw new Error('Reinstalled Node versions differ');
  return {packages:result.matching_versions,optional_other_platform_absent:result.absent_optional_other_platform.length};
}
async function phase(name,id){
  const loaded=load(),run=loaded.index.audits.find(a=>a.id===id&&a.kind==='DESKTOP_BUILDS_DEPENDENCY_REINSTALL'),review=loaded.index.audits.find(a=>a.id===reviewId);
  if(!run||os.hostname()!=='DESKTOP-SS5CURC')throw new Error('Rehearsal not found on development host');
  plain(assertRunRoot(run.root,id));
  assertNoRunningPhase(run);
  if(run.phases[name])throw new Error('Phase already attempted; no automatic retry');
  for(const pin of run.inputs)if(await hash(pin.path)!==pin.sha256)throw new Error('Rehearsal input changed');
  run.phases[name]={state:'RUNNING',at:new Date().toISOString()};run.state='RUNNING';save(loaded);
  const cmd=(label,exe,args,cwd=run.root)=>command(run,label,exe,args,cwd);
  try{
    if(name==='node'||name==='frontend'){
      const cwd=path.join(run.root,name);
      await cmd(name+'-ci',nodeExe,[npmCli,'ci','--ignore-scripts','--no-audit','--no-fund','--fetch-retries=0','--fetch-timeout=60000'],cwd);
      run.phases[name].versions=await verifyNode(run,review,name);
      // Keep lifecycle execution separate: scripts are reviewed before an explicit follow-up phase.
      run.phases[name].state='PACKAGES_INSTALLED_SCRIPTS_PENDING';
    }else if(name==='node-scripts'||name==='frontend-scripts'){
      const group=name==='node-scripts'?'node':'frontend';
      if(run.phases[group]?.state!=='PACKAGES_INSTALLED_SCRIPTS_PENDING')throw new Error('Package install prerequisite missing');
      const dir=path.join(run.root,group),old=path.join(review.checkout,'v2_next',group==='node'?'':'frontend');
      const scripts=group==='node'?['node_modules/electron/install.js','node_modules/electron-winstaller/script/select-7z-arch.js']:['node_modules/esbuild/install.js','node_modules/vite/node_modules/esbuild/install.js','node_modules/protobufjs/scripts/postinstall.js','scripts/patch_grafana_scenes_grid.js'];
      run.phases[name].script_hashes=[];
      for(let i=0;i<scripts.length;i++){
        const relative=scripts[i],file=path.join(dir,relative),sha=await hash(file);
        if(sha!==await hash(path.join(old,relative)))throw new Error('Reviewed lifecycle script differs');
        run.phases[name].script_hashes.push({relative,sha256:sha});
        const cwd=relative.includes('electron-winstaller')?path.join(dir,'node_modules/electron-winstaller'):dir;
        await cmd(group+'-hook-'+i,nodeExe,[file],cwd);
      }
      run.phases[name].state='PASS';
    }else if(name==='python'){
      const venv=path.join(run.root,'venv'),python=path.join(venv,'Scripts/python.exe');
      await cmd('python-venv',basePython,['-I','-m','venv',venv]);
      await cmd('python-download',python,['-I','-m','pip','download','--no-input','--only-binary=:all:','--no-deps','--no-cache-dir','--retries','0','--timeout','30','--index-url','https://pypi.org/simple','-r',path.join(run.root,'python-exact.txt'),'--dest',path.join(run.root,'wheels')]);
      run.wheels=[];for(const f of walk(path.join(run.root,'wheels')).files)run.wheels.push({path:f.path,bytes:f.bytes,sha256:await hash(f.path)});
      if(run.wheels.length!==review.python.distributions.length)throw new Error('Wheel count differs');
      const locked=review.python.distributions.map(d=>{
        const normalized=d.name.replaceAll('-','_').replaceAll('.','_').toLowerCase();
        const wheel=run.wheels.filter(w=>path.basename(w.path).toLowerCase().startsWith(normalized+'-'+d.version.toLowerCase()+'-'));
        if(wheel.length!==1)throw new Error('Wheel identity ambiguous');
        return d.name+'=='+d.version+' --hash=sha256:'+wheel[0].sha256.toLowerCase();
      }).join('\n')+'\n';
      fresh(path.join(run.root,'python-hashed.txt'),locked);
      await cmd('python-install',python,['-I','-m','pip','install','--no-input','--no-index','--no-deps','--no-compile','--require-hashes','--find-links',path.join(run.root,'wheels'),'-r',path.join(run.root,'python-hashed.txt')]);
      const list=await cmd('python-list',python,['-I','-m','pip','list','--format=json','--disable-pip-version-check']);
      const actual=JSON.parse(fs.readFileSync(list,'utf8')),norm=s=>s.toLowerCase().replace(/[-_.]+/g,'-');
      if(actual.length!==review.python.distributions.length||review.python.distributions.some(d=>!actual.some(a=>norm(a.name)===norm(d.name)&&a.version===d.version)))throw new Error('Python installed versions differ');
      await cmd('python-check',python,['-I','-m','pip','check']);
      run.phases[name].state='PASS';run.phases[name].packages=actual.length;
    }else if(name==='browsers'){
      if(run.phases.python?.state!=='PASS')throw new Error('Python reinstall prerequisite missing');
      await cmd('browser-install',path.join(run.root,'venv/Scripts/python.exe'),['-I','-m','playwright','install','chromium']);run.phases[name].state='PASS';
    }else throw new Error('Unknown phase');
  }catch(e){run.phases[name].state='FAILED';run.phases[name].reason=e.message;process.exitCode=1;}
  run.phases[name].finished_at=new Date().toISOString();run.state='AWAITING_REVIEW';save(loaded);
  console.log(JSON.stringify({id,phase:name,...run.phases[name]}));
}
async function reconcileFrontend(id){
  const loaded=load(),run=loaded.index.audits.find(a=>a.id===id),review=loaded.index.audits.find(a=>a.id===reviewId);
  if(!run||id!=='428c970f-1f0e-4127-802c-7b4ba9d621c0'||run.phases.frontend?.state!=='RUNNING'||run.phases.python?.state!=='PASS')throw new Error('Unexpected reconciliation state');
  plain(assertRunRoot(run.root,id));
  const log=path.join(run.root,'logs/frontend-ci.log');
  if(!/added 971 packages in \d+s/.test(fs.readFileSync(log,'utf8')))throw new Error('Successful install log missing');
  const versions=await verifyNode(run,review,'frontend');
  run.phases.frontend={...run.phases.frontend,state:'PACKAGES_INSTALLED_SCRIPTS_PENDING',versions,reconciled_at:new Date().toISOString(),reconciliation:'Optimistic registry save rejected concurrent Python phase update. Rechecked installed versions and log without repeating installation.',log,log_sha256:await hash(log)};
  save(loaded);console.log(JSON.stringify({phase:'frontend',state:run.phases.frontend.state,reinstalled:false,versions}));
}
function generatedDifference(group,name){
  name=name.replaceAll('\\','/');
  if(['node','frontend'].includes(group)&&name==='.package-lock.json')return 'NPM_INSTALL_METADATA';
  if(group==='browsers'&&/^\.links\/[0-9a-f]+$/.test(name))return 'PLAYWRIGHT_INSTALL_PATH_LINK';
  if(group==='python'){
    if(name.endsWith('.pyc')&&name.includes('/__pycache__/'))return 'PYTHON_BYTECODE_CACHE';
    if(/^Lib\/site-packages\/[^/]+\.dist-info\/(RECORD|REQUESTED)$/.test(name))return 'PIP_INSTALL_METADATA';
    if(name==='pyvenv.cfg'||/^Scripts\/(activate|Activate\.ps1|activate\.bat|deactivate\.bat)$/.test(name))return 'VENV_PATH_CONFIGURATION';
    if(/^Scripts\/[^/]+\.exe$/.test(name)&&!['Scripts/python.exe','Scripts/pythonw.exe'].includes(name))return 'PYTHON_ENTRYPOINT_LAUNCHER_PATH';
  }
  return null;
}
function launcherIdentity(bytes,venv){
  // distlib launchers: unchanged PE stub + path-bound shebang + one __main__.py ZIP member.
  const executable=path.join(venv,'Scripts','python.exe');
  const markers=['#!'+executable+'\n','#!"'+executable+'"\n'].map(line=>bytes.indexOf(Buffer.from(line))).filter(offset=>offset>=0);
  if(markers.length!==1)return null;
  const marker=markers[0],lineEnd=bytes.indexOf(10,marker);
  if(marker<0||lineEnd<0)return null;
  const line=bytes.subarray(marker,lineEnd).toString('utf8');
  if(!line.includes(path.join(venv,'Scripts','python.exe')))return null;
  let start=lineEnd+1;
  if(bytes[start]===13&&bytes[start+1]===10)start+=2;
  const separator=bytes.subarray(lineEnd+1,start).toString('hex'),end=bytes.length-22;
  if(end<start+30||bytes.readUInt32LE(start)!==0x04034b50||bytes.readUInt32LE(end)!==0x06054b50||bytes.readUInt16LE(end+10)!==1||bytes.readUInt16LE(end+20)!==0)return null;
  const method=bytes.readUInt16LE(start+8),size=bytes.readUInt32LE(start+18),nameLength=bytes.readUInt16LE(start+26),extraLength=bytes.readUInt16LE(start+28),body=start+30+nameLength+extraLength;
  if(bytes.subarray(start+30,start+30+nameLength).toString()!=='__main__.py'||size>65536||body+size>end||![0,8].includes(method))return null;
  const payload=bytes.subarray(body,body+size),main=method===8?inflateRawSync(payload,{maxOutputLength:65536}):payload;
  return {stub:digest(bytes.subarray(0,marker)),shebang:line.replace(venv,'<VENV>'),separator,main:digest(main)};
}
async function compare(id){
  const loaded=load(),run=loaded.index.audits.find(a=>a.id===id&&a.kind==='DESKTOP_BUILDS_DEPENDENCY_REINSTALL'),review=loaded.index.audits.find(a=>a.id===reviewId);
  if(!run||os.hostname()!=='DESKTOP-SS5CURC')throw new Error('Run not found');
  plain(assertRunRoot(run.root,id));assertNoRunningPhase(run);
  if(run.comparison)throw new Error('Comparison already recorded');
  run.state='COMPARING';save(loaded);
  try{
    const originalAudit=loaded.index.audits.find(a=>a.id==='48c1e9fe-4708-43d9-bf67-876199d9ffa8');
    const expected=new Map(originalAudit.files.filter(f=>f.classification==='CANDIDATE_REINSTALLABLE_DEPENDENCY').map(f=>[f.relative,f]));
    const result=[];let total=0;
    const observed=[];
    for(const [group,source,target] of [['node','node_modules','node/node_modules'],['frontend','frontend/node_modules','frontend/node_modules'],['python','backend/.venv','venv'],['browsers','backend/browsers','browsers']]){
      const oldRoot=plain(path.join(review.checkout,'v2_next',source)),newRoot=plain(path.join(run.root,target)),oldTree=walk(oldRoot),newTree=walk(newRoot);
      if(oldTree.errors.length||oldTree.links.length||newTree.errors.length||newTree.links.length)throw new Error('Incomplete comparison tree');
      const before=new Map(oldTree.files.map(f=>[path.relative(oldRoot,f.path),f])),after=new Map(newTree.files.map(f=>[path.relative(newRoot,f.path),f]));
      const groupResult={group,source:oldRoot,reinstalled:newRoot,matching_files:0,generated_differences:0,unexplained_differences:0,files:[]};
      for(const name of new Set([...before.keys(),...after.keys()])){
        const old=before.get(name),fresh=after.get(name),record={relative:name.replaceAll('\\','/'),source_bytes:old?.bytes??null,reinstalled_bytes:fresh?.bytes??null};
        if(old){
          const original=expected.get(path.relative(review.checkout,old.path).split(path.sep).join('/'));
          if(!original||original.bytes!==old.bytes||original.mtime_ms!==old.mtime_ms)throw new Error('Original dependency metadata changed');
          observed.push(old);record.source_sha256=await hash(old.path);
        }
        if(fresh)record.reinstalled_sha256=await hash(fresh.path);
        if(old&&fresh&&record.source_sha256===record.reinstalled_sha256){record.state='MATCH';groupResult.matching_files++;}
        else {
          record.generated_reason=generatedDifference(group,name);
          if(record.generated_reason==='PYTHON_ENTRYPOINT_LAUNCHER_PATH'){
            const left=old&&launcherIdentity(fs.readFileSync(old.path),oldRoot),right=fresh&&launcherIdentity(fs.readFileSync(fresh.path),newRoot);
            if(!left||!right||JSON.stringify(left)!==JSON.stringify(right))record.generated_reason=null;
            else record.launcher_identity=left;
          }
          record.state=record.generated_reason?'GENERATED_DIFFERENCE':'UNEXPLAINED_DIFFERENCE';
          if(record.generated_reason)groupResult.generated_differences++;else groupResult.unexplained_differences++;
        }
        groupResult.files.push(record);total++;
        if(total%5000===0)console.log('[COMPARE] '+total+' paths');
      }
      result.push(groupResult);
    }
    if(observed.length!==expected.size)throw new Error('Original file inventory incomplete');
    for(const f of observed){const s=fs.lstatSync(f.path);if(!s.isFile()||s.size!==f.bytes||s.mtimeMs!==f.mtime_ms)throw new Error('Original changed during comparison');}
    for(const pin of review.read_file_hashes)if(await hash(path.join(review.checkout,pin.relative))!==pin.sha256)throw new Error('Original audited input changed');
    const status=execFileSync('git',['--no-optional-locks','-c','core.fsmonitor=false','-C',review.checkout,'status','--porcelain=v1','-z','--untracked-files=all'],{encoding:'utf8'});
    if(status)throw new Error('Historical source worktree changed');
    const temporary=walk(run.root);if(temporary.errors.length||temporary.links.length)throw new Error('Incomplete temporary footprint');
    run.comparison={at:new Date().toISOString(),groups:result,original_files_unchanged:observed.length,source_worktree_clean:true,temporary_files:temporary.files.length,temporary_bytes:temporary.files.reduce((n,f)=>n+f.bytes,0)};
    const phases=['node','frontend','node-scripts','frontend-scripts','python','browsers'];
    const phasePass=phases.every(p=>['PASS','PACKAGES_INSTALLED_SCRIPTS_PENDING'].includes(run.phases[p]?.state));
    run.state=phasePass&&result.every(r=>r.unexplained_differences===0)?'COMPLETE':'COMPLETE_WITH_GAPS';
    run.acceptance='Dependency reinstall and content comparison only. No application build/runtime test or deletion approval.';
    run.completed_at=new Date().toISOString();
    loaded.index.history.push({kind:run.kind,audit_id:run.id,at:run.completed_at,state:run.state,deleted_files:0,remote_server_operations:0});save(loaded);
    console.log(JSON.stringify({id,state:run.state,original_files_unchanged:observed.length,temporary_bytes:run.comparison.temporary_bytes,groups:result.map(({files,...r})=>({...r,unexplained:files.filter(f=>f.state==='UNEXPLAINED_DIFFERENCE')}))}));
  }catch(e){run.state='STOPPED';run.error=e.message;save(loaded);throw e;}
}
async function recordCacheEvidence(id){
  const loaded=load(),run=loaded.index.audits.find(a=>a.id===id&&a.kind==='DESKTOP_BUILDS_DEPENDENCY_REINSTALL');
  if(!run||os.hostname()!=='DESKTOP-SS5CURC'||!['COMPLETE','COMPLETE_WITH_GAPS'].includes(run.state)||run.recovery_cache)throw new Error('Completed rehearsal required');
  plain(assertRunRoot(run.root,id));assertNoRunningPhase(run);
  const integrities=new Set(),archives=[];
  for(const group of ['node','frontend']){
    const hidden=JSON.parse(fs.readFileSync(path.join(run.root,group,'node_modules/.package-lock.json')));
    for(const item of Object.values(hidden.packages))integrities.add(item.integrity);
  }
  for(const integrity of integrities){
    if(!/^sha512-[A-Za-z0-9+/]+=*$/.test(integrity))throw new Error('Unexpected npm integrity');
    const encoded=integrity.slice(7),hex=Buffer.from(encoded,'base64').toString('hex');
    const file=plain(path.join(run.root,'npm-cache/_cacache/content-v2/sha512',hex.slice(0,2),hex.slice(2,4),hex.slice(4))),bytes=fs.readFileSync(file);
    if(crypto.createHash('sha512').update(bytes).digest('base64')!==encoded)throw new Error('npm cached archive differs');
    archives.push({relative:path.relative(run.root,file),bytes:bytes.length,integrity});
  }
  for(const wheel of run.wheels)if(await hash(wheel.path)!==wheel.sha256)throw new Error('Recovery wheel changed');
  run.recovery_cache={at:new Date().toISOString(),npm_archives:archives,wheels_verified:run.wheels.length,python_hashed_requirements_sha256:await hash(path.join(run.root,'python-hashed.txt')),offline_npm_reinstall_executed:false,browser_archives_preserved:false};
  run.tools={node:process.version,npm:JSON.parse(fs.readFileSync(path.join(path.dirname(npmCli),'../package.json'))).version,python_executable_sha256:await hash(basePython),rehearsal_script_sha256:await hash(__filename)};
  loaded.index.updated_at=new Date().toISOString();save(loaded);
  console.log(JSON.stringify({npm_archive_hashes_verified:archives.length,python_wheels_verified:run.wheels.length,registry_sha256:await hash(registry)}));
}
async function reviewGaps(id){
  const loaded=load(),run=loaded.index.audits.find(a=>a.id===id&&a.kind==='DESKTOP_BUILDS_DEPENDENCY_REINSTALL');
  if(!run||os.hostname()!=='DESKTOP-SS5CURC'||run.state!=='COMPLETE_WITH_GAPS'||run.gap_review)throw new Error('Unreviewed comparison gaps required');
  plain(assertRunRoot(run.root,id));
  const resolutions=[];
  for(const group of run.comparison.groups)for(const record of group.files.filter(f=>f.state==='UNEXPLAINED_DIFFERENCE')){
    const original=plain(path.join(group.source,record.relative));
    if(await hash(original)!==record.source_sha256)throw new Error('Original gap file changed');
    if(group.group==='python'&&record.relative.startsWith('Scripts/')&&record.relative.endsWith('.exe')){
      const installed=plain(path.join(group.reinstalled,record.relative));
      if(await hash(installed)!==record.reinstalled_sha256)throw new Error('Reinstalled launcher changed');
      const left=launcherIdentity(fs.readFileSync(original),group.source),right=launcherIdentity(fs.readFileSync(installed),group.reinstalled);
      if(!left||!right||JSON.stringify(left)!==JSON.stringify(right))throw new Error('Unexplained launcher content remains');
      resolutions.push({group:group.group,relative:record.relative,result:'SAME_PE_STUB_AND_ENTRYPOINT_INSTALL_PATH_DIFFERS',identity:left});
    }else if(group.group==='frontend'&&record.relative==='.vite/vitest/da39a3ee5e6b4b0d3255bfef95601890afd80709/results.json'){
      const bytes=fs.readFileSync(original),data=JSON.parse(bytes);
      if(bytes.length!==3449||digest(bytes)!=='E1BFBF970F7FCCCBF49F2B8AB125D527B881E6C4675473C92312DBE8F7693A81'||data.version!=='3.2.7'||data.results.length!==31)throw new Error('Unexpected historical Vitest evidence');
      const producer=path.join(group.source,'vitest/dist/chunks/cli-api.DVe0nWUx.js');
      if(!fs.readFileSync(producer,'utf8').includes('this.cachePath = resolve(config.dir, "results.json")'))throw new Error('Test cache producer differs');
      resolutions.push({group:group.group,relative:record.relative,result:'UNIQUE_HISTORICAL_TEST_CACHE_PRESERVED_INLINE',tests:31,producer:{path:producer,sha256:await hash(producer)},evidence:{encoding:'base64',bytes:bytes.length,sha256:digest(bytes),content:bytes.toString('base64')}});
    }else throw new Error('Unreviewed content difference');
  }
  if(resolutions.length!==22)throw new Error('Unexpected gap count');
  run.gap_review={at:new Date().toISOString(),result:'REINSTALL_VERIFIED_WITH_GENERATED_DIFFERENCES_AND_PRESERVED_TEST_EVIDENCE',resolutions,launcher_parser_correction:'Match the full interpreter shebang; the PE stub also contains a non-shebang #! string.',deleted_files:0,full_build_or_app_runtime_verified:false};
  loaded.index.history.push({kind:'DEPENDENCY_REINSTALL_GAPS_REVIEWED',audit_id:id,at:run.gap_review.at,result:run.gap_review.result,deleted_files:0});save(loaded);
  console.log(JSON.stringify({result:run.gap_review.result,launchers_verified:21,historical_test_files_preserved_inline:1,source_deletions:0}));
}
if(require.main===module){const [mode,id]=process.argv.slice(2);Promise.resolve().then(()=>mode==='prepare'?prepare():mode==='review-gaps'?reviewGaps(id):mode==='cache'?recordCacheEvidence(id):mode==='compare'?compare(id):mode==='reconcile-frontend'?reconcileFrontend(id):['node','frontend','python','browsers','node-scripts','frontend-scripts'].includes(mode)?phase(mode,id):Promise.reject(new Error('Unknown rehearsal phase'))).catch(e=>{console.error(e.message);process.exitCode=1;});}
module.exports={assertRunRoot,childEnvironment,assertNoRunningPhase,generatedDifference,launcherIdentity};
