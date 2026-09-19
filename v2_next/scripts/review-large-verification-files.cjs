// Read-only payload classification. The only write is an append to the single management JSON.
'use strict';
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),crypto=require('node:crypto');
const {execFileSync}=require('node:child_process');
const {walk,plain,hash,inside,assertMigrationStates,stageExtractionRecords}=require('./manage-verification-files.cjs');
const {stableKey}=require('./review-dist-artifacts.cjs');
const repo=path.resolve(__dirname,'..'),registry=path.join(repo,'verification-files.local.json');
const kind='LARGE_ARTIFACTS_READONLY_REVIEW_V1';
const digest=b=>crypto.createHash('sha256').update(b).digest('hex').toUpperCase();
const relative=p=>path.relative(repo,p).replaceAll('\\','/');
const member=(p,r)=>p===r||inside(p,r);
const attestationRoot=n=>`.tmp/internal_extended_running_state_attestation_r${n}`;
function selectGroups(files){
  const groups=new Map();
  for(const f of files){if(!/^(KEEP_(PACKAGE|UNRESOLVED|EVIDENCE)|HOLD_)/.test(f.decision))continue;
    const g=f.relative.split('/').slice(0,2).join('/');groups.set(g,(groups.get(g)||0)+f.bytes);
  }
  return [...groups].filter(([,bytes])=>bytes>=25000000).map(([g])=>g).sort();
}
function extractionSpecs(){
  const rows=[1,2,3,4,5].map(n=>({root:attestationRoot(n),source:n===1?'verify_extract_attempt2':'verify_extract',keeper:n===1?'package_attempt2':'package',producer:`${attestationRoot(n)}/build_r${n}.ps1`}));
  rows.push({root:attestationRoot(5),source:'expand_archive_verify',keeper:'package',producer:`${attestationRoot(5)}/verify_r5.ps1`});
  return rows;
}
function exactTree(source,keeper){
  if(!source.length||source.length!==keeper.length)return null;
  const names=new Map(keeper.map(f=>[f.name,f]));
  if(names.size!==keeper.length||new Set(source.map(f=>f.name)).size!==source.length)return null;
  if(source.some(f=>!names.has(f.name)||names.get(f.name).bytes!==f.bytes||names.get(f.name).sha256!==f.sha256))return null;
  return source.map(f=>({...f,retained_copy:{path:names.get(f.name).path,bytes:f.bytes,sha256:f.sha256}}));
}
function cacheCategory(relativePath){
  const m=relativePath.match(/^artifacts\/operator-emphasis-(?:isolation|optimization)-20260910\/run-[A-Za-z0-9]+\/electron-profile\/(Cache|Code Cache|GPUCache|DawnGraphiteCache|DawnWebGPUCache|Dictionaries)(?:\/|$)/);
  return m?m[1]:null;
}
function decide(f,c){
  if(c.protected.has(f.path.toLowerCase()))return 'PROTECT_PRIOR_KEEPER_OR_RECOVERY';
  if(c.tracked.has(f.path.toLowerCase()))return 'PROTECT_GIT_TRACKED';
  if(c.problemGroups.has(f.group))return 'HOLD_LINKED_OR_PARTIAL_GROUP';
  if(c.exact.has(f.path))return 'CANDIDATE_EXACT_VERIFICATION_EXTRACTION';
  if(/^\.tmp\/internal_extended_running_state_attestation_r[1-5]\/package(?:_|\/)/.test(f.relative))return 'KEEP_ATTESTATION_BUILD_INPUT_AND_LINEAGE';
  if(/^\.tmp\/internal_extended_running_state_attestation_r[1-5]\/.*verify/.test(f.relative))return 'KEEP_OTHER_EXTRACTION_ORIGIN_NOT_ESTABLISHED';
  if(cacheCategory(f.relative))return 'HOLD_TEST_CACHE_UNIT_AND_LIVE_USE_REVIEW';
  if(/^artifacts\/operator-emphasis-(isolation|optimization)-20260910\/.+\/electron-profile\//.test(f.relative))return 'KEEP_TEST_PROFILE_STATE_NOT_CACHE';
  if(f.group==='artifacts/spot-realtime-image-performance-v1.0.21-5971fc4')return 'KEEP_HISTORICAL_HASH_BOUND_RELEASE';
  if(f.relative==='.tmp/v1023-stage-helper-test-20260903/SmartFactoryLogger_v1.0.23_33c8db8_unsigned_internal_20260902T154936Z.zip')return 'KEEP_V1023_ARCHIVE_NO_VERIFIED_DUPLICATE';
  if(f.group==='artifacts/runtime_validation_20260720_080101_review'||/artifacts\/(review-20260904|v1025-v17-120m-readonly-audit)/.test(f.group)||f.group==='.tmp/v9_zero_image_replay_20260901')return 'KEEP_DIAGNOSTIC_OR_REPLAY_EVIDENCE';
  if(f.group==='.tmp/v1026-python-audit-tool-20260911')return 'KEEP_TOOL_ENVIRONMENT_REQUIRES_DEPENDENCY_REVIEW';
  if(/^\.tmp\/internal_extended_running_state_attestation_r[1-5]\//.test(f.relative))return 'KEEP_ATTESTATION_OUTPUT_OR_BUILD_SOURCE';
  return 'KEEP_OTHER_BENCHMARK_OR_VALIDATION_EVIDENCE';
}
function totals(files){
  const states={};for(const f of files){const s=states[f.decision]??={files:0,bytes:0};s.files++;s.bytes+=f.bytes;}return states;
}
function inventory(groups){
  return groups.map(group=>{
    const root=path.resolve(repo,group);plain(root);const t=walk(root);
    return {group,root,files:t.files.map(f=>({path:f.path,relative:relative(f.path),group,bytes:f.bytes,snapshot:stableKey(fs.lstatSync(f.path,{bigint:true}))})).sort((a,b)=>a.path.localeCompare(b.path)),directories:t.dirs.sort(),links:t.links.sort((a,b)=>a.path.localeCompare(b.path)),errors:t.errors.sort((a,b)=>a.path.localeCompare(b.path))};
  });
}
async function review(expected,record){
  if(process.platform!=='win32'||os.hostname()!=='DESKTOP-SS5CURC'||!/^[A-F0-9]{64}$/.test(expected))throw Error('Wrong host/hash');
  if(await hash(registry)!==expected)throw Error('External management hash differs');
  const index=JSON.parse(fs.readFileSync(registry,'utf8'));assertMigrationStates(index);
  if(index.workspace!==repo||index.host!==os.hostname()||index.plans.some(p=>p.state!=='COMPLETE')||index.audits.some(a=>a.kind===kind))throw Error('Management state differs/already recorded');
  const previous=index.audits.find(a=>a.id==='dde4f1ce-375f-4be5-84a8-18b47bcf2745');if(!previous)throw Error('Previous classification missing');
  const groups=selectGroups(previous.files);
  console.log('[1/4] Inventory the large unresolved groups without following links or inspecting operating profiles.');
  const before=inventory(groups),files=before.flatMap(t=>t.files),byPath=new Map(files.map(f=>[f.path,f]));
  const tracked=new Set(execFileSync('git',['--no-optional-locks','-c','core.fsmonitor=false','ls-files','-z'],{cwd:repo,encoding:'utf8',windowsHide:true,maxBuffer:20000000}).split('\0').filter(Boolean).map(p=>path.resolve(repo,p).toLowerCase()));
  const protectedPaths=new Set(index.plans.flatMap(p=>p.files.filter(f=>f.retained_copy).map(f=>f.retained_copy.toLowerCase())));
  for(const f of previous.files)if(f.decision.startsWith('PROTECT_'))protectedPaths.add(f.path.toLowerCase());
  for(const a of stageExtractionRecords(index))for(const f of a.files)protectedPaths.add(f.keeper.toLowerCase());
  for(const m of index.migrations)for(const f of m.files)if(f.destination)protectedPaths.add(f.destination.toLowerCase());
  for(const a of index.audits.filter(a=>a.kind==='DESKTOP_BUILDS_DEPENDENCY_CLEANUP_PLAN'))for(const f of a.keep_files)protectedPaths.add(path.join(a.keep_root,...f.relative.split('/')).toLowerCase());
  const problemGroups=new Set(before.filter(t=>t.links.length||t.errors.length).map(t=>t.group));
  const checked=new Map(),sourceWitnesses=new Map();
  async function verified(p){
    if(checked.has(p))return checked.get(p);
    const f=byPath.get(p);if(!f)throw Error('Content witness outside selected inventory');
    const s=fs.lstatSync(plain(p),{bigint:true});if(!s.isFile()||s.nlink!==1n||stableKey(s)!==f.snapshot)throw Error('File changed or hardlinked');
    const value={...f,sha256:await hash(p)};if(stableKey(fs.lstatSync(p,{bigint:true}))!==f.snapshot)throw Error('Witness changed');checked.set(p,value);return value;
  }
  async function source(p){
    p=path.resolve(repo,p);plain(p);const s=fs.lstatSync(p,{bigint:true});if(s.size>5000000n)throw Error('Bounded source read exceeded');
    const b=fs.readFileSync(p);if(stableKey(fs.lstatSync(p,{bigint:true}))!==stableKey(s))throw Error('Source changed');
    sourceWitnesses.set(p,{path:p,sha256:digest(b),snapshot:stableKey(s)});return b.toString('utf8');
  }
  console.log('[2/4] Compare complete verifier extraction trees with their same-revision package inputs.');
  const exact=new Map(),treeComparisons=[],producerEvidence=[];
  for(const spec of extractionSpecs()){
    const root=path.resolve(repo,spec.root);if(problemGroups.has(spec.root))throw Error('Candidate group has a link/error');
    const code=await source(spec.producer);
    const anchors=spec.source==='expand_archive_verify'?['$expandRoot = Join-Path $workRoot "expand_archive_verify"','Expand-Archive -LiteralPath $zipPath -DestinationPath $expandRoot']:['$packageRoot = Join-Path $workRoot "'+spec.keeper+'"','$verifyRoot = Join-Path $workRoot "'+spec.source+'"','[IO.Compression.ZipFile]::ExtractToDirectory($zipPath, $verifyRoot)'];
    if(anchors.some(a=>!code.includes(a)))throw Error('Extraction producer differs');
    producerEvidence.push({source:spec.producer,anchors,meaning:'Builder/verifier creates an extraction of its published package for verification. No helper is executed by this review.'});
    const src=path.join(root,spec.source),keep=path.join(root,spec.keeper);
    async function members(base){const rows=[];for(const f of files.filter(f=>inside(f.path,base))){rows.push({...await verified(f.path),name:path.relative(base,f.path).replaceAll('\\','/')});}return rows;}
    const sourceFiles=await members(src),keeperFiles=await members(keep),mapped=exactTree(sourceFiles,keeperFiles);
    treeComparisons.push({root:src,keeper_root:keep,source_files:sourceFiles.length,keeper_files:keeperFiles.length,bytes:sourceFiles.reduce((n,f)=>n+f.bytes,0),complete_relative_name_length_hash_match:!!mapped});
    if(mapped)for(const f of mapped)exact.set(f.path,f.retained_copy);
  }
  console.log('[3/4] Preserve historical releases, original diagnostics and benchmark results; separate test caches from state.');
  for(const variant of ['isolation','optimization']){
    const base=`artifacts/operator-emphasis-${variant}-20260910`;
    const build=await source(base+'/build-and-run.cjs'),main=await source(base+'/electron-main.cjs');
    if(!build.includes("fs.mkdtempSync(path.join(__dirname, 'run-'))")||!main.includes("'electron-profile'")||!main.includes("app.setPath('userData'"))throw Error('Isolated profile producer differs');
    producerEvidence.push({source:base+'/electron-main.cjs',meaning:'userData is placed in a validated per-run electron-profile, not the operating AppData profile. Cache deletion remains held pending whole-cache units, live use and preservation review.'});
  }
  await source('docs/03-analysis/runtime-error-root-cause-validation.analysis.md');
  const collector=await source('scripts/collect-spot-connecttimeout-evidence.ps1');if(!collector.includes("Join-Path $sanitizedRoot 'spot_tcp_brief_redacted.txt'"))throw Error('Diagnostic producer differs');
  producerEvidence.push({source:'scripts/collect-spot-connecttimeout-evidence.ps1',meaning:'The large text file is sanitized packet evidence for a documented incident, not an application cache.'});
  const release='artifacts/spot-realtime-image-performance-v1.0.21-5971fc4';
  const sums=await source(release+'/SHA256SUMS.txt');
  for(const line of sums.trim().split(/\r?\n/)){
    const m=/^([a-fA-F0-9]{64})\s+([^\\/:]+)$/.exec(line);if(!m||m[2]==='.'||m[2]==='..')throw Error('Release checksum syntax differs');
    const f=await verified(path.join(repo,release,m[2]));if(f.sha256!==m[1].toUpperCase())throw Error('Historical release hash differs');
  }
  const releaseReport=await source('docs/04-report/spot-realtime-image-performance-deployment-5971fc4.report.md');
  if(!releaseReport.includes('01CF544C999FB21FADB7F36965DC35FB9E8AEE36D1EEBD3319A1EB7296AD191A'))throw Error('Release documentation binding differs');
  const largeFiles=[];
  for(const f of files.filter(f=>f.bytes>=10000000&&!problemGroups.has(f.group))){const v=await verified(f.path);largeFiles.push({path:f.path,bytes:f.bytes,sha256:v.sha256});}
  const contentGroups=new Map();for(const f of largeFiles){const k=f.bytes+'|'+f.sha256;if(!contentGroups.has(k))contentGroups.set(k,[]);contentGroups.get(k).push(f.path);}
  const duplicateClusters=[...contentGroups].filter(([,v])=>v.length>1).map(([k,paths])=>({bytes_per_file:Number(k.split('|')[0]),sha256:k.split('|')[1],paths,interpretation:'Exact bytes in inspected large files only; not independent deletion authority. Package inputs and indexed cache members stay protected/held.'}));
  // Search source/reference text, never arbitrary log bodies or archive contents.
  const referencePaths=new Set(['package.json','README.md','AGENTS.md'].map(p=>path.join(repo,p)));
  for(const b of ['scripts','docs','../.github/workflows']){const t=walk(path.resolve(repo,b));if(t.links.length||t.errors.length)throw Error('Repository reference coverage incomplete');for(const f of t.files)if(/\.(ps1|psm1|cjs|js|py|md|json|ya?ml)$/i.test(f.path))referencePaths.add(f.path);}
  for(const t of before)if(!problemGroups.has(t.group))for(const f of t.files)if(/\.(ps1|psm1|cjs|js|py|md)$/i.test(f.path)&&f.bytes<=5000000&&!/\/(electron-profile|sessionData|site-packages|node_modules)\//.test(f.relative))referencePaths.add(f.path);
  const referenceHits=[];
  for(const p of [...referencePaths].sort()){
    const text=await source(p),lines=text.split(/\r?\n/);
    for(const group of groups){const name=group.split('/')[1].toLowerCase();lines.forEach((line,n)=>{if(line.toLowerCase().includes(name))referenceHits.push({source:relative(p),line:n+1,group});});}
  }
  const context={protected:protectedPaths,tracked,problemGroups,exact};
  const records=files.map(f=>({...f,decision:decide(f,context),content_verified_this_review:checked.has(f.path),...(checked.has(f.path)?{sha256:checked.get(f.path).sha256}:{}),...(exact.has(f.path)?{retained_copy:exact.get(f.path)}:{}),...(cacheCategory(f.relative)?{cache_unit:cacheCategory(f.relative)}:{})}));
  const at=new Date().toISOString(),audit={id:crypto.randomUUID(),kind,at,state:'CLASSIFIED_NOT_DELETION_APPROVED',previous_review_id:previous.id,original_index_sha256:expected,
    selection:'Groups with >=25,000,000 unresolved logical bytes in the previous classification. No whole-disk or complete remaining-files claim.',
    scope:before.map(t=>({group:t.group,root:t.root,files:t.files.length,bytes:t.files.reduce((n,f)=>n+f.bytes,0),links:t.links,errors:t.errors})),files:records,summary:totals(records),tree_comparisons:treeComparisons,producer_evidence:producerEvidence,large_file_duplicate_clusters:duplicateClusters,
    source_witnesses:[...sourceWitnesses.values()],literal_reference_hits:referenceHits,deleted_files:0,deleted_bytes:0,moved_files:0,existing_acl_writes:0,remote_server_operations:0,deletion_authorized:false,
    limitations:['Content equality alone is not permission to delete. Candidate payload must pass fresh exclusive-open, ADS/link, ACL, live process/service/task/shortcut and keeper-reference checks before a separately approved deletion.','Links are not followed. Linked/partial groups remain held, including unrelated files in the same selected group.','Only candidate/keeper trees, release checksums and ordinary files >=10MB outside linked groups are content-hashed. Others receive preservation classifications only.','Literal reference searches include repository and selected artifact harness sources; dynamic or external consumers are not fully observable. Non-UTF8 source bytes retain ASCII path tokens; this is not a semantic parser.','Cache members are not loose-file deletion candidates even if they match dictionaries; cache indexes and profile state require unit-level review.','Older attempts without a matching retained producer definition remain kept; current builder definitions are not retroactively attributed to them.','Archive files were hashed as files, not expanded or executed. Operational backups, installed programs and running server were not accessed.','Append-only audit/history update; previous global summary and inventory are not presented as freshly rescanned.']};
  console.log('[4/4] Recheck unchanged membership and witness metadata; append classification without payload changes.');
  if(JSON.stringify(inventory(groups))!==JSON.stringify(before))throw Error('Selected payload metadata/membership changed');
  for(const w of sourceWitnesses.values())if(stableKey(fs.lstatSync(w.path,{bigint:true}))!==w.snapshot||await hash(w.path)!==w.sha256)throw Error('Source witness changed');
  if(await hash(registry)!==expected)throw Error('Concurrent management update');
  if(record){
    index.audits.push(audit);index.history.push({at,kind,audit_id:audit.id,state:audit.state,deleted_files:0,deleted_bytes:0,moved_files:0});index.updated_at=at;
    const fd=fs.openSync(registry+'.writing','wx');try{fs.writeFileSync(fd,JSON.stringify(index));fs.fsyncSync(fd);}finally{fs.closeSync(fd);}
    if(await hash(registry)!==expected)throw Error('Concurrent management update; preserve .writing');fs.renameSync(registry+'.writing',registry);
  }
  console.log(JSON.stringify({id:audit.id,state:audit.state,recorded:record,scope_groups:groups.length,readable_files:files.length,logical_bytes:files.reduce((n,f)=>n+f.bytes,0),summary:audit.summary,tree_comparisons:treeComparisons,content_verified_files:checked.size,reference_sources:sourceWitnesses.size,linked_or_partial_groups:[...problemGroups],deleted_files:0,index_sha256:await hash(registry)},null,2));
}
if(require.main===module){const [mode,pin,...extra]=process.argv.slice(2);if(!['--read','--record'].includes(mode)||extra.length)throw Error('Use --read/--record INDEX_SHA256');review(pin,mode==='--record').catch(e=>{console.error('LARGE_REVIEW_HOLD: '+e.message);process.exitCode=1;});}
module.exports={selectGroups,extractionSpecs,exactTree,cacheCategory,decide,totals};
