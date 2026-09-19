// Plan only. No file deletion, migration, install, product or device calls.
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),crypto=require('node:crypto');
const {execFileSync}=require('node:child_process');
const {plain,walk,assertMigrationStates}=require('./manage-verification-files.cjs');
const repo=path.resolve(__dirname,'..'),registry=path.join(repo,'verification-files.local.json');
const runId='428c970f-1f0e-4127-802c-7b4ba9d621c0';
const slash=p=>p.split(path.sep).join('/'),digest=bytes=>crypto.createHash('sha256').update(bytes).digest('hex').toUpperCase();
function child(root,relative){
  if(typeof relative!=='string'||!relative||relative.includes('\\')||relative.includes(':')||relative.split('/').some(x=>!x||x==='.'||x==='..')||/[\x00-\x1f]/.test(relative))throw new Error('Noncanonical child path');
  const full=path.resolve(root,...relative.split('/'));
  if(!full.toLowerCase().startsWith(root.toLowerCase()+path.sep))throw new Error('Child escaped boundary');return full;
}
function targets(checkout,runRoot){
  return [
    ['old-node',path.join(checkout,'v2_next/node_modules'),'node','source'],
    ['old-frontend',path.join(checkout,'v2_next/frontend/node_modules'),'frontend','source'],
    ['old-python',path.join(checkout,'v2_next/backend/.venv'),'python','source'],
    ['old-browsers',path.join(checkout,'v2_next/backend/browsers'),'browsers','source'],
    ['test-node',path.join(runRoot,'node/node_modules'),'node','reinstalled'],
    ['test-frontend',path.join(runRoot,'frontend/node_modules'),'frontend','reinstalled'],
    ['test-python',path.join(runRoot,'venv'),'python','reinstalled'],
    ['test-node-cache',path.join(runRoot,'temp/node-compile-cache'),null,null]
  ].map(([id,root,group,side])=>({id,root,group,side}));
}
function inTarget(file,roots){return roots.some(r=>file.toLowerCase().startsWith(r.root.toLowerCase()+path.sep));}
function stable(before,after){return before.size===after.size&&before.mtimeNs===after.mtimeNs&&before.ctimeNs===after.ctimeNs&&before.ino===after.ino&&before.dev===after.dev;}
function assertReinstallComplete(run){
  if(run?.gap_review?.result!=='REINSTALL_VERIFIED_WITH_GENERATED_DIFFERENCES_AND_PRESERVED_TEST_EVIDENCE')throw new Error('Reinstall review incomplete');
  for(const key of ['node','frontend'])if(!['PASS','PACKAGES_INSTALLED_SCRIPTS_PENDING'].includes(run.phases?.[key]?.state))throw new Error('Package phase incomplete');
  for(const key of ['python','node-scripts','frontend-scripts','browsers'])if(run.phases?.[key]?.state!=='PASS')throw new Error('Required reinstall phase incomplete');
  if(Object.values(run.phases).some(p=>!['PASS','PACKAGES_INSTALLED_SCRIPTS_PENDING'].includes(p.state)))throw new Error('Unexpected incomplete phase');
}
function readFingerprint(file){
  // Parent topology is verified by the caller's complete non-link inventory and rechecked later.
  const before=fs.lstatSync(file,{bigint:true});if(!before.isFile()||before.isSymbolicLink())throw new Error('Non-file fingerprint target');
  const fd=fs.openSync(file,'r'),h=crypto.createHash('sha256'),buffer=Buffer.allocUnsafe(1024*1024);
  try{
    if(!stable(before,fs.fstatSync(fd,{bigint:true})))throw new Error('Opened file identity changed');
    let count;while((count=fs.readSync(fd,buffer,0,buffer.length,null))>0)h.update(buffer.subarray(0,count));
    if(!stable(before,fs.fstatSync(fd,{bigint:true}))||!stable(before,fs.lstatSync(file,{bigint:true})))throw new Error('File changed while hashing');
  }finally{fs.closeSync(fd);}
  return {bytes:Number(before.size),sha256:h.digest('hex').toUpperCase(),mtime_ns:before.mtimeNs.toString(),ctime_ns:before.ctimeNs.toString(),birthtime_ns:before.birthtimeNs.toString()};
}
function checkedWalk(root){plain(root);const result=walk(root);if(result.links.length||result.errors.length)throw new Error('Incomplete or linked tree');return result;}
function recheckTree(root,before){
  const after=checkedWalk(root),files=new Map(before.files.map(f=>[f.path,f])),dirs=new Set(before.dirs);
  if(after.files.length!==files.size||after.dirs.length!==dirs.size||after.dirs.some(d=>!dirs.has(d))||after.files.some(f=>{const b=files.get(f.path);return !b||b.bytes!==f.bytes||b.mtime_ms!==f.mtime_ms;}))throw new Error('Tree changed during planning');
}
async function plan(){
  plain(registry);const raw=fs.readFileSync(registry),originalHash=digest(raw),index=JSON.parse(raw);
  if(os.hostname()!=='DESKTOP-SS5CURC'||index.host!==os.hostname()||index.workspace!==repo)throw new Error('Development host/workspace mismatch');
  assertMigrationStates(index);
  if(index.audits.some(a=>a.kind==='DESKTOP_BUILDS_DEPENDENCY_CLEANUP_PLAN'))throw new Error('A dependency cleanup plan already exists; review it instead');
  const run=index.audits.find(a=>a.id===runId),review=index.audits.find(a=>a.id===run?.review_id);
  if(!run||!review||run.root!==path.join(repo,'.tmp','dep-'+runId)||run.gap_review?.result!=='REINSTALL_VERIFIED_WITH_GENERATED_DIFFERENCES_AND_PRESERVED_TEST_EVIDENCE')throw new Error('Reinstall review incomplete');
  assertReinstallComplete(run);
  const checkout=path.join(os.homedir(),'Desktop/SmartFactoryLogger_Builds/spot-tcp-connection-reuse-remediation_bfd9be7/source');
  if(run.checkout!==checkout||Object.values(run.phases).some(p=>!['PASS','PACKAGES_INSTALLED_SCRIPTS_PENDING'].includes(p.state)))throw new Error('Reviewed paths/phases differ');
  const git=args=>execFileSync('git',['--no-optional-locks','-c','core.fsmonitor=false','-C',checkout,...args],{encoding:'utf8',timeout:60000,maxBuffer:30e6});
  const head=git(['rev-parse','HEAD']).trim();if(head!=='bfd9be785f7a87aa4150445945861a54bca98f33'||git(['status','--porcelain=v1','-z','--untracked-files=all']))throw new Error('Original checkout changed');
  const tracked=new Set(git(['ls-files','-z']).split('\0').filter(Boolean));
  const ignored=new Set(git(['ls-files','--others','--ignored','--exclude-standard','-z']).split('\0').filter(Boolean));
  const roots=targets(checkout,run.root),inventories=new Map(),remove=[];
  let total=0;
  for(const spec of roots){
    const tree=checkedWalk(spec.root);inventories.set(spec.root,tree);
    const group=run.comparison.groups.find(g=>g.group===spec.group);
    if(group&&group[spec.side]!==spec.root)throw new Error('Comparison target mapping differs');
    const prior=new Map((group?.files||[]).filter(f=>f[spec.side+'_bytes']!==null).map(f=>[f.relative,f]));
    if(group&&prior.size!==tree.files.length)throw new Error('Compared file set changed');
    for(const file of tree.files){
      const relative=slash(path.relative(spec.root,file.path));if(child(spec.root,relative)!==file.path)throw new Error('Noncanonical inventory');
      if(spec.side==='source'){
        const historical=slash(path.relative(checkout,file.path));if(tracked.has(historical)||!ignored.has(historical))throw new Error('Source target is tracked or no longer ignored');
      }
      if(spec.id==='test-node-cache'&&!/^v22\.22\.2-x64-9ac5647c\/[0-9a-f]{8}$/.test(relative))throw new Error('Unexpected generated cache path');
      const info=readFingerprint(file.path),expected=prior.get(relative);
      if(group&&(!expected||expected[spec.side+'_bytes']!==info.bytes||expected[spec.side+'_sha256']!==info.sha256))throw new Error('Reinstall comparison hash changed');
      remove.push({root_id:spec.id,relative,...info});total++;
      if(total%20000===0)console.log('[PLAN] hashed '+total+' candidate files');
    }
  }
  console.log('[PLAN] Verifying retained recovery files and embedded evidence.');
  const allRun=checkedWalk(run.root),keep=[];
  for(const file of allRun.files)if(!inTarget(file.path,roots))keep.push({relative:slash(path.relative(run.root,file.path)),...readFingerprint(file.path)});
  const kept=new Map(keep.map(f=>[f.relative,f]));
  for(const archive of run.recovery_cache.npm_archives){
    const relative=slash(archive.relative),record=kept.get(relative);if(!record||record.bytes!==archive.bytes)throw new Error('npm recovery archive not retained');
    const bytes=fs.readFileSync(child(run.root,relative));if('sha512-'+crypto.createHash('sha512').update(bytes).digest('base64')!==archive.integrity)throw new Error('npm cache integrity differs');
  }
  for(const wheel of run.wheels){const entry=kept.get(slash(path.relative(run.root,wheel.path)));if(!entry||entry.sha256!==wheel.sha256)throw new Error('Recovery wheel differs');}
  const electron=keep.filter(f=>f.relative.startsWith('electron-cache/'));
  if(electron.length!==1||electron[0].sha256!=='5531ADAFD7183D0D5C5C4BC3F563346B41A96AA3ACD0D0EA98D0375808292F88')throw new Error('Electron recovery archive differs');
  const browser=run.comparison.groups.find(g=>g.group==='browsers');
  for(const file of browser.files.filter(f=>f.reinstalled_bytes!==null)){
    const record=kept.get('browsers/'+file.relative);if(!record||record.sha256!==file.reinstalled_sha256)throw new Error('Browser recovery file differs');
  }
  const embedded=run.gap_review.resolutions.filter(r=>r.evidence).map(r=>r.evidence);
  if(embedded.length!==1)throw new Error('Unique evidence missing');
  for(const e of embedded){const bytes=Buffer.from(e.content,'base64');if(bytes.length!==e.bytes||digest(bytes)!==e.sha256)throw new Error('Embedded evidence differs');}
  for(const pin of run.inputs){const entry=kept.get(slash(path.relative(run.root,pin.path)));if(!entry||entry.sha256!==pin.sha256)throw new Error('Reinstall input not retained');}
  if(kept.get('python-hashed.txt')?.sha256!==run.recovery_cache.python_hashed_requirements_sha256)throw new Error('Python recovery recipe differs');
  const outsideAnchors=[];
  for(const pin of review.read_file_hashes){const file=child(checkout,pin.relative);if(inTarget(file,roots))continue;const info=readFingerprint(plain(file));if(info.sha256!==pin.sha256)throw new Error('Retained source anchor differs');outsideAnchors.push({path:file,...info});}
  const classification=index.audits.find(a=>a.id==='48c1e9fe-4708-43d9-bf67-876199d9ffa8');
  for(const packageRecord of classification.packages){const file=child(checkout,packageRecord.relative),info=readFingerprint(plain(file));if(info.sha256!==packageRecord.sha256)throw new Error('Historical package differs');outsideAnchors.push({path:file,...info});}
  console.log('[PLAN] Reading observable process/service/task/shortcut references.');
  const usage=JSON.parse(execFileSync('pwsh.exe',['-NoLogo','-NoProfile','-File',path.join(__dirname,'read-dependency-use.ps1')],{encoding:'utf8',windowsHide:true,timeout:120000,maxBuffer:2e6}));
  for(const [root,tree] of inventories)recheckTree(root,tree);recheckTree(run.root,allRun);
  if(git(['rev-parse','HEAD']).trim()!==head||git(['status','--porcelain=v1','-z','--untracked-files=all']))throw new Error('Original source changed');
  const id=crypto.randomUUID(),at=new Date().toISOString();
  const groups=roots.map(r=>{const files=remove.filter(f=>f.root_id===r.id);return {...r,files:files.length,bytes:files.reduce((n,f)=>n+f.bytes,0),directories:inventories.get(r.root).dirs.map(d=>slash(path.relative(r.root,d)))};});
  const audit={id,kind:'DESKTOP_BUILDS_DEPENDENCY_CLEANUP_PLAN',at,state:usage.matches.length?'PLANNED_BLOCKED_BY_REFERENCES':'PLAN_COMPLETE_AWAITING_APPROVAL',reinstall_audit_id:runId,head,checkout,roots:groups,files:remove,keep_root:run.root,keep_files:keep,source_anchors:outsideAnchors,usage,counts:{candidate_files:remove.length,candidate_bytes:remove.reduce((n,f)=>n+f.bytes,0),retained_run_files:keep.length,retained_run_bytes:keep.reduce((n,f)=>n+f.bytes,0)},recovery:{npm_archive_count:run.recovery_cache.npm_archives.length,python_wheel_count:run.wheels.length,browser_files:browser.files.filter(f=>f.reinstalled_bytes!==null).length,electron_archive_sha256:electron[0].sha256,embedded_test_evidence_sha256:embedded[0].sha256,recipe:'Original tracked source and lockfiles stay. Recreate Node with pinned lockfiles/cache and reviewed hooks; recreate Python 3.12.6 using python-hashed.txt plus wheels; restore browsers from retained browsers tree with path links regenerated. No existing helper is promised to run after dependency cleanup.'},deletion_approved:false,deletion_ready:false,deleted_files:0,moved_files:0,remote_server_operations:0,predelete_requirements:['Separate approval of this exact manifest.','Fresh path/link/content/metadata/ACL/alternate-stream and live-use checks.','Preserve all keep records, embedded evidence and original Git/source/package witnesses.','Use durable per-file deletion journaling; stop on drift, no recursive wildcard cleanup.'],limitations:['No full build/application runtime acceptance; this is development dependency cleanup only.','Generated bytecode, installation metadata/timestamps and path-bound launchers are regenerated, not promised bit-identical recovery.','Unreadable process metadata, global open handles and shell working directories are not proved unused.','ACL and alternate streams have not yet been reviewed for these deletion targets.','Retained recovery files remain at their recorded rehearsal paths and must not be treated as generic temporary garbage; canonical migration is separate.']};
  audit.tooling=['plan-dependency-cleanup.cjs','read-dependency-use.ps1','manage-verification-files.cjs'].map(name=>({path:path.join(__dirname,name),...readFingerprint(plain(path.join(__dirname,name)))}));
  if(digest(fs.readFileSync(registry))!==originalHash)throw new Error('Concurrent registry change');
  index.audits.push(audit);index.history.push({kind:audit.kind,audit_id:id,at,state:audit.state,deleted_files:0,moved_files:0});index.updated_at=at;
  const fd=fs.openSync(registry+'.writing','wx');try{fs.writeFileSync(fd,JSON.stringify(index));fs.fsyncSync(fd);}finally{fs.closeSync(fd);}fs.renameSync(registry+'.writing',registry);
  console.log(JSON.stringify({id,state:audit.state,counts:audit.counts,groups:groups.map(({directories,...r})=>r),usage,deleted_files:0,registry_sha256:digest(fs.readFileSync(registry))}));
}
if(require.main===module)plan().catch(e=>{console.error(e.message);process.exitCode=1;});
module.exports={child,targets,inTarget,stable,readFingerprint,assertReinstallComplete};
