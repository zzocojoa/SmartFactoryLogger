// Records the already approved, exact development-PC migration. Never copies/deletes a candidate.
'use strict';
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),crypto=require('node:crypto');
const {execFileSync}=require('node:child_process');
const {plain,walk,hash,assertMigrationStates}=require('./manage-verification-files.cjs');
const {references,specs}=require('./plan-dist-cleanup.cjs');
const {proposal,reviewId}=require('./plan-dist-acl-scope.cjs');
const repo=path.resolve(__dirname,'..'),registry=path.join(repo,'verification-files.local.json');
const kind='DESKTOP_DIST_PROTECTED_CI_MIGRATION';
const tools=['migrate-dist-protected.ps1','dist-migration-core.ps1','read-dist-use.ps1','server-path-audit/cleanup-archive-core.ps1'];
function contract(index){
  const old=index.audits.find(a=>a.id===reviewId),scope=index.audits.find(a=>a.id==='4cfa13f4-2b5c-443f-ae7b-44da3918dcc5');
  if(old?.state!=='PLAN_REVIEW_HOLD'||scope?.state!=='SCOPE_REVIEW_COMPLETE_ALTERNATIVE_NEEDS_DECISION'||old.cleanup)throw new Error('Prior scope differs');
  const p=proposal(old),copies=p.groups.flatMap(g=>g.files),bySource=new Map(copies.map(f=>[f.path,f]));
  const remove=[...copies.map(f=>({...f,action:'MIGRATE_ORIGINAL',keeper:f.destination})),...old.files.map(f=>{
    const keep=bySource.get(f.retained_copy.path);
    if(!keep||keep.sha256!==f.sha256||keep.bytes!==f.bytes)throw new Error('Duplicate mapping differs');
    return {...f,action:'REMOVE_DUPLICATE',keeper:keep.destination};
  })].map(f=>{
    const m=scope.metadata.find(m=>m.path===f.path);
    if(!m||m.sha256!==f.sha256||m.bytes!==f.bytes)throw new Error('Missing reviewed metadata');
    return {path:f.path,bytes:f.bytes,sha256:f.sha256,action:f.action,keeper:f.keeper,metadata:m};
  });
  if(remove.length!==21||copies.length!==12||new Set(remove.map(f=>f.path.toLowerCase())).size!==21||
    copies.reduce((n,f)=>n+f.bytes,0)!==2126941124||remove.filter(f=>f.action==='REMOVE_DUPLICATE').reduce((n,f)=>n+f.bytes,0)!==744244326)throw new Error('Fixed counts/bytes differ');
  for(const s of specs)if(!remove.some(f=>f.path===path.join(repo,'dist',s.relative)&&f.keeper===path.join(p.archive_root,...s.keeper.split('/'))))throw new Error('Fixed name/mapping differs');
  return {root:old.root,archive_root:p.archive_root,new_directories:p.new_directories,groups:p.groups,files:remove,
    existing_boundaries:scope.acl_boundaries.filter(r=>r.exists).map(r=>({path:r.path,sddl:r.sddl})),
    copied_files:12,copied_bytes:2126941124,source_files_to_remove:21,duplicate_files:9,net_logical_bytes_freed:744244326};
}
async function prepare(expected,record){
  if(os.hostname()!=='DESKTOP-SS5CURC'||process.platform!=='win32')throw new Error('Wrong development host');
  if(await hash(registry)!==expected)throw new Error('External index SHA256 mismatch');
  const index=JSON.parse(fs.readFileSync(registry,'utf8'));assertMigrationStates(index);
  if(index.host!==os.hostname()||index.workspace!==repo||index.audits.some(a=>a.kind===kind)||index.plans.some(a=>a.state!=='COMPLETE'))throw new Error('Unexpected/pending index');
  const plan=contract(index);
  for(const dir of plan.new_directories)if(fs.existsSync(dir))throw new Error('Archive path already exists; preserve and review');
  const original=index.audits.find(a=>a.id==='3cdfb7ed-2ce7-45c6-983f-c18d2a6c0e9c');
  const refs=references(original);
  if(refs.skipped.length||refs.review_digest!=='17D45B45265BD295322D6B25A6F484CCD69ED8E295433FDBEF52252EE60ACEE9')throw new Error('Previously reviewed references changed');
  console.log('[1/3] Rehash the exact 21 approved files; no payload mutation.');
  for(const f of plan.files){plain(f.path);if(fs.statSync(f.path).size!==f.bytes||await hash(f.path)!==f.sha256)throw new Error('Source bytes differ');}
  const tree=walk(plan.root);if(tree.errors.length||tree.links.length||tree.files.length!==3836)throw new Error('dist membership differs');
  const use=JSON.parse(execFileSync('pwsh.exe',['-NoProfile','-File',path.join(__dirname,'read-dist-use.ps1')],{encoding:'utf8',windowsHide:true,timeout:90000,maxBuffer:2e6}));
  if(use.matches.length)throw new Error('Observed active dist reference');
  // Metadata witnesses for every preserved file, not just the removed subset.
  const ps=String.raw`$ErrorActionPreference='Stop';[Console]::InputEncoding=[Text.UTF8Encoding]::new($false);[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false);$rows=foreach($p in ([Console]::In.ReadToEnd()|ConvertFrom-Json)){$f=Get-Item -LiteralPath $p -Force;[pscustomobject]@{path=$p;bytes=$f.Length;creation_utc_ticks=$f.CreationTimeUtc.Ticks.ToString();last_write_utc_ticks=$f.LastWriteTimeUtc.Ticks.ToString();attributes=[int]$f.Attributes;sddl=(Get-Acl -LiteralPath $p).Sddl}};ConvertTo-Json -InputObject @($rows) -Compress`;
  console.log('[2/3] Record unchanged dist metadata, source reference witnesses and tooling hashes.');
  const outside=JSON.parse(execFileSync('pwsh.exe',['-NoProfile','-Command',ps],{input:JSON.stringify(tree.files.map(f=>f.path)),encoding:'utf8',windowsHide:true,timeout:120000,maxBuffer:12e6}));
  const at=new Date().toISOString(),audit={id:crypto.randomUUID(),kind,at,state:'PREPARED',host:os.hostname(),workspace:repo,
    approval:'User approved four complete CI sets (12 files) copied/verified into the new private archive, followed by removing their 12 originals and nine exact duplicates. Existing ACLs and all directories remain unchanged.',
    prior_review_id:reviewId,prior_scope_id:'4cfa13f4-2b5c-443f-ae7b-44da3918dcc5',original_registry_sha256:expected,plan,
    outside_files:outside,directories:tree.dirs,reference_witnesses:refs.witnesses.map(w=>({path:path.resolve(repo,w.source),sha256:w.sha256})),usage:use,
    tooling:await Promise.all(tools.map(async source=>({path:path.join(__dirname,source),sha256:await hash(path.join(__dirname,source))}))),
    copied_files:0,removed_source_files:0,deleted_files:0,deleted_bytes:0,moved_files:0,existing_acl_writes:0,remote_server_operations:0,
    required_operator_validation:'Run dist-migration.test.ps1 in administrator PowerShell 7; require PASS and administrator_acl_copy_tests=True before -Execute.',
    validation_tooling:await Promise.all(['dist-migration.test.ps1','dist-migration.test.cjs','prepare-dist-migration.cjs','manage-verification-files.cjs'].map(async source=>({path:path.join(__dirname,source),sha256:await hash(path.join(__dirname,source))}))),
    limitation:'Same-disk preservation, not disaster recovery. Administrative execution and all fresh preconditions still required. PREPARED is not completion.'};
  console.log('[3/3] Publish preparation only to the existing single management file.');
  if(await hash(registry)!==expected)throw new Error('Concurrent index change');
  if(record){
    index.audits.push(audit);index.history.push({at,kind,audit_id:audit.id,state:'PREPARED',deleted_files:0,deleted_bytes:0,moved_files:0});index.updated_at=at;
    const out=fs.openSync(registry+'.writing','wx');try{fs.writeFileSync(out,JSON.stringify(index));fs.fsyncSync(out);}finally{fs.closeSync(out);}
    if(await hash(registry)!==expected)throw new Error('Concurrent index change; preserve staging file');
    fs.renameSync(registry+'.writing',registry);
  }
  console.log(JSON.stringify({state:record?'PREPARED':'READ_ONLY_PREFLIGHT_PASS',id:audit.id,recorded:record,source_files:21,keepers:12,existing_acl_writes:0,deleted_files:0,index_sha256:await hash(registry)}));
}
if(require.main===module){const [mode,pin,...extra]=process.argv.slice(2);if(!['--read','--record'].includes(mode)||extra.length)throw new Error('Use --read/--record INDEX_SHA256');prepare(pin,mode==='--record').catch(e=>{console.error('DIST_PREPARE_HOLD: '+e.message);process.exitCode=1;});}
module.exports={contract,kind};
