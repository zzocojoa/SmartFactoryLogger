// Read-only dist classification; --record appends only to the single local registry.
// No deletion, extraction, package execution, network, ACL changes or server access.
'use strict';
const fs=require('node:fs');
const path=require('node:path');
const os=require('node:os');
const crypto=require('node:crypto');
const {execFileSync}=require('node:child_process');
const {plain,walk,hash,inside,assertMigrationStates}=require('./manage-verification-files.cjs');
const repo=path.resolve(__dirname,'..');
const root=path.join(repo,'dist');
const registry=path.join(repo,'verification-files.local.json');
const canonical=path.join(repo,'artifacts','server-evidence');
const key=r=>`${r.bytes}|${r.sha256}`;
const lower=p=>p.toLowerCase();
function stableKey(s){return [s.size,s.mtimeNs,s.ctimeNs,s.birthtimeNs,s.ino,s.dev,s.nlink].map(String).join('|');}
function inventory(base){
  plain(base);const items=walk(base);
  if(items.links.length||items.errors.length)throw new Error('Incomplete or linked audit tree; preserve it');
  return {files:items.files.map(f=>({path:f.path,relative:path.relative(base,f.path).replaceAll('\\','/'),bytes:f.bytes,snapshot:stableKey(fs.lstatSync(f.path,{bigint:true}))})).sort((a,b)=>a.relative.localeCompare(b.relative)),directories:items.dirs.sort()};
}
function protectedReason(relative,tracked=false){
  if(tracked)return 'PROTECT_GIT_TRACKED';
  if(/^(?:win-unpacked|SmartFactory_Portable)\//i.test(relative))return 'PROTECT_REFERENCED_BUILD_TREE';
  if(/^ci-[^/]+\//i.test(relative))return 'KEEP_COMPLETE_CI_RELEASE_SET';
  return null;
}
function classify(record,{tracked=false,copy=null,runtimeHits=0}={}){
  const reason=protectedReason(record.relative,tracked);
  if(reason)return reason;
  if(runtimeHits)return 'HOLD_OBSERVED_RUNTIME_REFERENCE';
  if(copy&&copy.path!==record.path&&key(copy)===key(record))return 'CANDIDATE_EXACT_DUPLICATE_REQUIRES_REFERENCE_REVIEW';
  if(/\.(?:exe|zip|7z|blockmap)$/i.test(record.relative))return 'KEEP_PACKAGE_WITHOUT_VERIFIED_RETAINED_COPY';
  return 'KEEP_UNIQUE_OR_UNRESOLVED_EVIDENCE';
}
function selectCopy(record,pool){
  return pool.filter(p=>lower(p.path)!==lower(record.path)&&key(p)===key(record))
    .sort((a,b)=>Number(b.external)-Number(a.external)||Number(path.basename(b.path)===path.basename(record.path))-Number(path.basename(a.path)===path.basename(record.path))||a.path.localeCompare(b.path))[0]||null;
}
function summarize(records){
  const decisions={},groups={};
  for(const r of records){
    const d=decisions[r.decision]??={files:0,bytes:0};d.files++;d.bytes+=r.bytes;
    const g=groups[r.relative.split('/')[0]]??={files:0,bytes:0,candidate_files:0,candidate_bytes:0};g.files++;g.bytes+=r.bytes;
    if(r.decision.startsWith('CANDIDATE_')){g.candidate_files++;g.candidate_bytes+=r.bytes;}
  }
  return {files:records.length,bytes:records.reduce((n,r)=>n+r.bytes,0),decisions,groups};
}
function sourcePaths(){
  const files=[path.join(repo,'package.json'),path.join(repo,'README.md')];
  for(const base of [path.join(repo,'scripts'),path.join(repo,'docs'),path.join(repo,'..','.github','workflows')]){
    const items=walk(base);
    if(items.errors.length||items.links.length)throw new Error('Static reference tree incomplete');
    files.push(...items.files.filter(f=>/\.(?:ps1|psm1|cjs|js|md|json|ya?ml)$/i.test(f.path)&&!/-dist-(?:artifacts|use)(?:\.test)?\./.test(f.path)).map(f=>f.path));
  }
  return [...new Set(files)].sort();
}
async function staticReferences(groups){
  const witnesses=[],references=[];
  for(const file of sourcePaths()){
    plain(file);if(fs.statSync(file).size>5e6)throw new Error('Static source too large for bounded audit');
    const before=stableKey(fs.lstatSync(file,{bigint:true}));
    const bytes=fs.readFileSync(file);
    if(before!==stableKey(fs.lstatSync(file,{bigint:true})))throw new Error('Static source changed');
    const relative=path.relative(path.dirname(repo),file).replaceAll('\\','/');
    witnesses.push({source:relative,sha256:crypto.createHash('sha256').update(bytes).digest('hex').toUpperCase()});
    bytes.toString('utf8').split(/\r?\n/).forEach((line,i)=>{
      const normalized=line.toLowerCase().replaceAll('\\','/');
      for(const name of groups)if(normalized.includes(name.toLowerCase()))references.push({source:relative,line:i+1,dist_group:name});
    });
  }
  return {witnesses,references,coverage:'Literal top-level dist names in current scripts/docs/workflows/package/README. Matches may be historical; dynamic paths, external scripts, old tool invocations and references inside archives are not fully resolved. No source contents copied.'};
}
async function review({record=false,expected}={}){
  if(process.platform!=='win32'||os.hostname()!=='DESKTOP-SS5CURC')throw new Error('Development host mismatch');
  plain(registry);const original=await hash(registry);
  if(!/^[A-F0-9]{64}$/.test(expected||'')||original!==expected)throw new Error('External registry SHA256 differs');
  const index=JSON.parse(fs.readFileSync(registry,'utf8'));assertMigrationStates(index);
  if(index.host!==os.hostname()||index.workspace!==repo||(index.plans||[]).some(p=>p.state!=='COMPLETE'))throw new Error('Management state is not complete');
  const before=inventory(root);
  const previous=index.files.filter(f=>inside(f.path,root));
  if(previous.length!==before.files.length||previous.some(f=>!before.files.some(r=>r.path===f.path&&r.bytes===f.bytes)))throw new Error('dist differs from the latest inventory; review the change first');
  const tracked=new Set(execFileSync('git',['-c','core.fsmonitor=false','ls-files','-z'],{cwd:repo,encoding:'utf8',env:{...process.env,GIT_OPTIONAL_LOCKS:'0'},windowsHide:true}).split('\0').filter(Boolean).map(p=>lower(path.resolve(repo,p))));
  console.log('[1/4] Hash exact dist inventory; no package/helper execution.');
  const records=[];let n=0;
  for(const item of before.files){records.push({...item,sha256:await hash(item.path)});if(++n%500===0)console.log(`[HASH] ${n}/${before.files.length}`);}
  console.log('[2/4] Verify retained canonical copies with matching sizes.');
  const sizes=new Set(records.map(r=>r.bytes));const retained=[];const seen=new Set();
  for(const m of index.migrations||[]){
    if(m.state!=='COMPLETE')throw new Error('Migration is incomplete');
    for(const f of m.files.filter(f=>f.destination&&sizes.has(f.bytes))){
      if(!inside(f.destination,canonical))throw new Error('Retained copy is outside the canonical evidence root');
      if(seen.has(lower(f.destination)))continue;seen.add(lower(f.destination));
      plain(f.destination);const snapshot=stableKey(fs.lstatSync(f.destination,{bigint:true}));
      const sha256=await hash(f.destination);
      if(sha256!==f.sha256||fs.statSync(f.destination).size!==f.bytes)throw new Error('Retained migration evidence changed');
      retained.push({path:f.destination,bytes:f.bytes,sha256,snapshot,external:true});
    }
  }
  // Internal keepers are fixed, complete CI sets; never another candidate or a build staging tree.
  const keepPool=[...retained,...records.filter(r=>/^ci-[^/]+\//i.test(r.relative)).map(r=>({...r,external:false}))];
  const buckets=new Map();for(const p of keepPool){if(!buckets.has(key(p)))buckets.set(key(p),[]);buckets.get(key(p)).push(p);}
  console.log('[3/4] Read static and observable host references; no process changes.');
  const staticInfo=await staticReferences([...new Set(records.map(r=>r.relative.split('/')[0]))]);
  const usage=JSON.parse(execFileSync('pwsh.exe',['-NoLogo','-NoProfile','-File',path.join(__dirname,'read-dist-use.ps1')],{cwd:repo,encoding:'utf8',windowsHide:true,timeout:90000,maxBuffer:2e6}));
  for(const r of records){
    const copy=selectCopy(r,buckets.get(key(r))||[]);
    r.decision=classify(r,{tracked:tracked.has(lower(r.path)),copy,runtimeHits:usage.matches.length});
    r.retained_copy=copy?{path:copy.path,bytes:copy.bytes,sha256:copy.sha256,external:copy.external}:null;
    r.static_reference_count=staticInfo.references.filter(s=>s.dist_group===r.relative.split('/')[0]).length;
  }
  console.log('[4/4] Recheck exact membership and read witnesses; append audit only when requested.');
  if(JSON.stringify(inventory(root))!==JSON.stringify(before))throw new Error('dist changed during classification');
  for(const r of retained)if(stableKey(fs.lstatSync(r.path,{bigint:true}))!==r.snapshot)throw new Error('Retained copy changed during classification');
  for(const w of staticInfo.witnesses)if(await hash(path.resolve(repo,'..',w.source))!==w.sha256)throw new Error('Static source changed during classification');
  if(await hash(registry)!==original)throw new Error('Concurrent registry update');
  const id=crypto.randomUUID(),at=new Date().toISOString(),summary=summarize(records);
  const audit={id,kind:'DESKTOP_DIST_READONLY_CLASSIFICATION',at,state:'CLASSIFIED_NOT_APPROVED_FOR_DELETION',root,original_registry_sha256:original,summary,files:records,retained_copies_verified:retained.length,static_references:staticInfo,usage,deleted_files:0,moved_files:0,acl_writes:0,remote_server_operations:0,deletion_authorized:false,limitations:[
    'Exact byte duplicate is only a candidate. Package provenance, path-bound helper/evidence references and fresh use/ACL/ADS/exclusive-open checks remain required before a separately approved deletion.',
    'No archives were extracted or their members compared. Missing external copies do not prove uniqueness inside archives.',
    'Current build staging paths and complete CI sets are preserved regardless of duplicate bytes. This is not operational acceptance or permission to run a historical installer.',
    'Live read-only hashes and metadata rechecks are not an atomic snapshot or proof that every process or external reference is known.'
  ]};
  audit.tooling=await Promise.all(['review-dist-artifacts.cjs','read-dist-use.ps1','review-dist-artifacts.test.cjs'].map(async p=>({source:p,sha256:await hash(path.join(__dirname,p))})));
  if(record){
    index.audits.push(audit);index.history.push({at,kind:audit.kind,audit_id:id,state:audit.state,deleted_files:0,deleted_bytes:0,moved_files:0});index.updated_at=at;
    const staging=registry+'.writing';plain(path.dirname(registry));
    if(await hash(registry)!==original)throw new Error('Concurrent registry update before audit publication');
    const fd=fs.openSync(staging,'wx');
    try{fs.writeFileSync(fd,JSON.stringify(index));fs.fsyncSync(fd);}finally{fs.closeSync(fd);}
    if(await hash(registry)!==original)throw new Error('Concurrent registry update; preserve staging audit');
    fs.renameSync(staging,registry);
  }
  console.log(JSON.stringify({id,state:audit.state,recorded:record,summary,retained_copies_verified:retained.length,static_reference_sources:staticInfo.witnesses.length,static_reference_hits:staticInfo.references.length,usage,deleted_files:0,index_sha256:record?await hash(registry):original},null,2));
  return audit;
}
if(require.main===module){
  const args=process.argv.slice(2);const mode=args.shift(),expected=args.shift();
  if(!['--read','--record'].includes(mode)||args.length){console.error('Use --read or --record followed by the external registry SHA256');process.exitCode=1;}
  else review({record:mode==='--record',expected}).catch(e=>{console.error('DIST_REVIEW_HOLD: '+e.message);process.exitCode=1;});
}
module.exports={stableKey,protectedReason,classify,selectCopy,summarize};
