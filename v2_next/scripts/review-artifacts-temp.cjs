// Classification only. Candidate/source files are never copied, moved, deleted or executed.
'use strict';
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),crypto=require('node:crypto');
const {execFileSync}=require('node:child_process');
const {walk,plain,hash,inside,assertMigrationStates}=require('./manage-verification-files.cjs');
const {stableKey}=require('./review-dist-artifacts.cjs');
const repo=path.resolve(__dirname,'..'),registry=path.join(repo,'verification-files.local.json');
const kind='ARTIFACTS_TMP_READONLY_CLASSIFICATION';
const roots=['artifacts','.tmp'].map(p=>path.join(repo,p));
const deliveryRoots=[1,2].map(n=>path.join(repo,'artifacts','v1026-server-stage-20260911-r'+n));
const extractionRoots=[4,5].map(n=>path.join(repo,'.tmp','v26stage-tests-r'+n,'actual-transfer'));
const digest=b=>crypto.createHash('sha256').update(b).digest('hex').toUpperCase();
const same=(a,b)=>a.toLowerCase()===b.toLowerCase();
const under=(p,r)=>same(p,r)||inside(p,r);
function entryPath(base,name){
  if(typeof name!=='string'||!name||/[\\:\x00-\x1f]/.test(name)||name.split('/').some(s=>!s||s==='.'||s==='..'||/[ .]$/.test(s)))throw new Error('Noncanonical member name');
  const p=path.resolve(base,...name.split('/'));if(!inside(p,base))throw new Error('Member escaped base');return p;
}
function inventory(){
  return roots.map(root=>{
    plain(root);const t=walk(root);
    return {root,files:t.files.map(f=>({path:f.path,relative:path.relative(repo,f.path).replaceAll('\\','/'),bytes:f.bytes,snapshot:stableKey(fs.lstatSync(f.path,{bigint:true}))})).sort((a,b)=>a.path.localeCompare(b.path)),directories:t.dirs.sort(),links:t.links.sort((a,b)=>a.path.localeCompare(b.path)),errors:t.errors.sort((a,b)=>a.path.localeCompare(b.path))};
  });
}
function classification(record,context){
  const p=record.path,r=record.relative;
  if(context.tracked.has(p.toLowerCase()))return 'PROTECT_GIT_TRACKED';
  if(context.retained.has(p.toLowerCase()))return 'PROTECT_PREVIOUS_CLEANUP_KEEPER';
  if(context.migrated.has(p.toLowerCase()))return 'PROTECT_MIGRATED_SERVER_EVIDENCE';
  if(context.recovery.some(base=>under(p,base)))return 'PROTECT_DEPENDENCY_RECOVERY';
  if(r.startsWith('.tmp/v1026x1/')||r.startsWith('artifacts/v1026-release-prep-d7a1b20-20260911/'))return 'PROTECT_CURRENT_HELPER_BUILD_INPUT_AND_RELEASE';
  if(r.startsWith('artifacts/server-evidence/'))return 'PROTECT_CANONICAL_SERVER_EVIDENCE';
  if(r.startsWith('artifacts/v1026-electron44-local-validation-20260911/'))return 'KEEP_CURRENT_VALIDATION_EVIDENCE';
  if(deliveryRoots.some(base=>under(p,base)))return 'KEEP_HASH_BOUND_STAGE_DELIVERY';
  if(context.exact.has(p))return 'CANDIDATE_EXACT_TEST_EXTRACTION_PENDING_DELETE_REVIEW';
  if(context.problemGroups.has(r.split('/').slice(0,2).join('/')))return 'HOLD_LINKED_OR_PARTIAL_GROUP';
  if(/\.(?:ini|bak)$/i.test(r))return 'KEEP_CONFIGURATION_OR_BACKUP_REQUIRES_REVIEW';
  if(/\.(?:json|jsonl|csv|log|txt|md|pcapng|etl|png|jpe?g|webm|html)$/i.test(r))return 'KEEP_EVIDENCE_NOT_PROVEN_DISPOSABLE';
  if(/\.(?:zip|7z|exe|dll|whl|tgz|blockmap)$/i.test(r))return 'KEEP_PACKAGE_OR_BINARY_NOT_YET_REVIEWED';
  return 'KEEP_UNRESOLVED_REQUIRES_REVIEW';
}
function matchExtraction(files,pools){
  // Whole 32-member tree equality, including names; never mix different revisions or compare basenames.
  for(const pool of pools){
    if(files.length!==32||pool.files.length!==32)continue;
    const byName=new Map(pool.files.map(f=>[f.name,f]));
    if(byName.size!==32||files.some(f=>!byName.has(f.name)||byName.get(f.name).bytes!==f.bytes||byName.get(f.name).sha256!==f.sha256))continue;
    return files.map(f=>({...f,keeper:byName.get(f.name).path,delivery_root:pool.root,archive:pool.archive}));
  }
  return null;
}
function summarize(files){
  const decisions={},groups={};
  for(const f of files){
    const d=decisions[f.decision]??={files:0,bytes:0};d.files++;d.bytes+=f.bytes;
    const key=f.relative.split('/').slice(0,2).join('/'),g=groups[key]??={files:0,bytes:0,candidate_files:0,candidate_bytes:0};g.files++;g.bytes+=f.bytes;
    if(f.decision.startsWith('CANDIDATE_')){g.candidate_files++;g.candidate_bytes+=f.bytes;}
  }
  return {readable_files:files.length,logical_bytes:files.reduce((n,f)=>n+f.bytes,0),decisions,groups};
}
function sources(){
  const files=[path.join(repo,'package.json'),path.join(repo,'README.md'),path.join(repo,'AGENTS.md')];
  for(const root of [path.join(repo,'scripts'),path.join(repo,'docs'),path.resolve(repo,'../.github/workflows')]){
    const t=walk(root);if(t.errors.length||t.links.length)throw new Error('Source/reference coverage incomplete');
    files.push(...t.files.filter(f=>/\.(ps1|psm1|cjs|js|md|json|ya?ml)$/i.test(f.path)&&!/[\\/]review-artifacts-temp(?:\.test)?\.cjs$/.test(f.path)).map(f=>f.path));
  }
  return [...new Set(files)].sort();
}
async function staticReferences(groupNames){
  const witnesses=[],hits=[];
  for(const p of sources()){
    plain(p);if(fs.statSync(p).size>5e6)throw new Error('Source exceeds bounded read budget');
    const snapshot=stableKey(fs.lstatSync(p,{bigint:true})),b=fs.readFileSync(p),source=path.relative(repo,p).replaceAll('\\','/');
    if(stableKey(fs.lstatSync(p,{bigint:true}))!==snapshot)throw new Error('Source changed');
    witnesses.push({source,sha256:digest(b),snapshot});
    const text=b.toString('utf8').toLowerCase(),lines=text.split(/\r?\n/);
    for(const group of groupNames){const name=group.split('/')[1].toLowerCase();if(name.length<5||!text.includes(name))continue;
      lines.forEach((line,i)=>{if(line.includes(name))hits.push({source,line:i+1,group});});
    }
  }
  return {witnesses,hits,coverage:'Literal group-name references in repository scripts/docs/workflows/README/package. Name hits are not proof of an active consumer; dynamic/custom/external references and archive contents are not fully inspected.'};
}
async function review(expected,record){
  if(os.hostname()!=='DESKTOP-SS5CURC'||process.platform!=='win32')throw new Error('Wrong development host');
  if(await hash(registry)!==expected)throw new Error('External management SHA256 differs');
  const index=JSON.parse(fs.readFileSync(registry,'utf8'));assertMigrationStates(index);
  if(index.host!==os.hostname()||index.workspace!==repo||index.plans.some(p=>p.state!=='COMPLETE')||index.audits.some(a=>a.kind===kind))throw new Error('Unexpected or already recorded management state');
  console.log('[1/4] Inventory artifacts and .tmp without following links; preserve inaccessible boundaries.');
  const before=inventory(),all=before.flatMap(t=>t.files),facts=new Map(all.map(f=>[f.path,f]));
  const tracked=new Set(execFileSync('git',['--no-optional-locks','-c','core.fsmonitor=false','ls-files','-z'],{cwd:repo,encoding:'utf8',windowsHide:true,maxBuffer:20e6}).split('\0').filter(Boolean).map(p=>path.resolve(repo,p).toLowerCase()));
  const retained=new Set(index.plans.flatMap(p=>p.files.filter(f=>f.retained_copy).map(f=>f.retained_copy.toLowerCase())));
  const migrated=new Set(index.migrations.filter(m=>m.state==='COMPLETE').flatMap(m=>m.files.filter(f=>f.destination).map(f=>f.destination.toLowerCase())));
  const recovery=index.audits.filter(a=>a.kind==='DESKTOP_BUILDS_DEPENDENCY_CLEANUP_PLAN').map(a=>a.keep_root);
  const checked=new Map();
  async function verify(p,bytes,sha){
    if(checked.has(p)){const f=checked.get(p);if(f.bytes!==bytes||f.sha256!==sha)throw new Error('Conflicting pin');return f;}
    const f=facts.get(p);if(!f||f.bytes!==bytes||fs.lstatSync(p).nlink!==1)throw new Error('File count/size/link differs');
    const actual=await hash(p);if(actual!==sha)throw new Error('File hash differs');const result={...f,sha256:actual};checked.set(p,result);return result;
  }
  const pools=[],extractions=[];
  console.log('[2/4] Verify two retained delivery sets and compare the two 32-file test extractions.');
  for(const root of deliveryRoots){
    const resultPath=path.join(root,'build-result.json'),b=JSON.parse(fs.readFileSync(plain(resultPath),'utf8'));
    const receipt=await verify(resultPath,fs.statSync(resultPath).size,await hash(resultPath));
    if(b.archive.entry_count!==32||b.archive.entries.length!==32||path.dirname(b.archive.path)!==root||b.product_commit!=='d7a1b20f96711fb07fc7add0867e79ee36506fce')throw new Error('Stage delivery contract differs');
    const archive=await verify(b.archive.path,b.archive.length,b.archive.sha256);
    if(fs.readFileSync(plain(b.archive.path+'.sha256.txt'),'utf8').trim()!==archive.sha256)throw new Error('Stage sidecar differs');
    await verify(b.archive.path+'.sha256.txt',fs.statSync(b.archive.path+'.sha256.txt').size,await hash(b.archive.path+'.sha256.txt'));
    const payload=path.join(root,'transfer-files'),members=[];
    for(const e of b.archive.entries){const f=await verify(entryPath(payload,e.name),e.length,e.sha256);members.push({...f,name:e.name});}
    if(new Set(members.map(f=>f.path)).size!==32||all.filter(f=>inside(f.path,payload)).length!==32)throw new Error('Retained delivery member set differs');
    pools.push({root,files:members,archive:{path:archive.path,bytes:archive.bytes,sha256:archive.sha256},build_result_sha256:receipt.sha256});
  }
  const exact=new Map();
  for(const root of extractionRoots){
    const members=all.filter(f=>inside(f.path,root));
    if(members.length!==32||before.some(t=>[...t.links,...t.errors].some(e=>under(e.path,root))))throw new Error('Extraction boundary differs');
    const reportPath=path.join(path.dirname(root),'test-result.json'),report=JSON.parse(fs.readFileSync(plain(reportPath),'utf8'));
    if(report.result!=='V1026_STAGE_LOCAL_FIXTURES_PASS'||!report.tests.includes('actual-transfer-contract')||report.live_server_queries_performed!==false)throw new Error('Test origin is not supported by its receipt');
    await verify(reportPath,fs.statSync(reportPath).size,await hash(reportPath));
    const candidates=[];
    for(const f of members)candidates.push({...await verify(f.path,f.bytes,await hash(f.path)),name:path.relative(root,f.path).replaceAll('\\','/')});
    const mapped=matchExtraction(candidates,pools);
    if(mapped)for(const f of mapped)exact.set(f.path,f);
    extractions.push({root,files:members.length,bytes:members.reduce((n,f)=>n+f.bytes,0),complete_name_length_hash_match:!!mapped,retained_delivery:mapped?.[0].delivery_root||null,test_receipt:reportPath,test_receipt_retained:true});
  }
  const problemGroups=new Set(before.flatMap(t=>[...t.links,...t.errors]).map(e=>path.relative(repo,e.path).replaceAll('\\','/').split('/').slice(0,2).join('/')));
  const context={tracked,retained,migrated,recovery,exact,problemGroups};
  const records=all.map(f=>({...f,decision:classification(f,context),content_verified_this_review:checked.has(f.path),...(checked.has(f.path)?{sha256:checked.get(f.path).sha256}:{}),...(exact.has(f.path)?{retained_copy:{path:exact.get(f.path).keeper,bytes:f.bytes,sha256:exact.get(f.path).sha256}}:{})}));
  const summary=summarize(records);
  console.log('[3/4] Read producer/consumer references and preserve prior keeper dependencies.');
  const references=await staticReferences(Object.keys(summary.groups));
  const at=new Date().toISOString(),audit={id:crypto.randomUUID(),kind,at,state:'CLASSIFIED_PARTIAL_COVERAGE_NOT_DELETION_APPROVED',original_registry_sha256:expected,
    scope:before.map(t=>({root:t.root,readable_files:t.files.length,logical_bytes:t.files.reduce((n,f)=>n+f.bytes,0),directories:t.directories.length,links:t.links,errors:t.errors,complete:t.errors.length===0&&t.links.length===0})),
    summary,files:records,stage_extractions:extractions,verified_deliveries:pools,static_references:references,
    producer_evidence:[{source:'scripts/server-stage-v1026/test-stage.ps1',anchor:"$full=Join-Path $root 'actual-transfer'",meaning:'Test expands the hash-checked delivery into a dedicated fixture; preserves test-result.json outside actual-transfer.'},{source:'scripts/server-stage-v1026/build-transfer.ps1',anchor:"$payload=Join-Path $output 'transfer-files'",meaning:'Versioned delivery builder retains complete transfer-files, ZIP, sidecar and build receipt.'},{source:'scripts/server-stage-v1026/build-installed-read-v1026.ps1',anchor:".tmp\\v1026x1\\app",meaning:'Current helper build requires this extracted application and the pinned release candidate.'}],
    deleted_files:0,deleted_bytes:0,moved_files:0,acl_writes:0,remote_server_operations:0,deletion_authorized:false,
    limitations:['Readable-path classification only, not a whole-disk or fully accessible inventory. Links were not traversed; inaccessible test data remains held.','Only the 64 test extraction candidates and their delivery/receipt/sidecar witnesses were content-verified. All other KEEP classifications are preservation decisions, not a new full integrity pass.','Archive bytes were hashed against build receipts; ZIP members were not decompressed or executed. Candidate retention points to verified ordinary files, not unverified archive entries.','Deletion requires separate exact scope approval and fresh process/service/task/shortcut, ACL, alternate-stream, exclusive-open and retained-reference checks. No mutation is authorized by this audit.','Single management file updated only by appending this audit/history; previous global inventory/summary and protected archive verification were not rerun.']};
  for(const e of audit.producer_evidence)if(!fs.readFileSync(path.join(repo,e.source),'utf8').includes(e.anchor))throw new Error('Producer anchor changed');
  console.log('[4/4] Recheck unchanged inventory/witnesses and append classification only.');
  if(JSON.stringify(inventory())!==JSON.stringify(before))throw new Error('Payload membership/metadata changed during audit');
  if(JSON.stringify(sources())!==JSON.stringify(references.witnesses.map(w=>path.resolve(repo,w.source)).sort()))throw new Error('Source membership changed');
  for(const w of references.witnesses)if(stableKey(fs.lstatSync(path.resolve(repo,w.source),{bigint:true}))!==w.snapshot)throw new Error('Source metadata changed');
  if(await hash(registry)!==expected)throw new Error('Concurrent management update');
  audit.tooling=await Promise.all(['review-artifacts-temp.cjs','review-artifacts-temp.test.cjs'].map(async source=>({source,sha256:await hash(path.join(__dirname,source))})));
  if(record){
    index.audits.push(audit);index.history.push({at,kind,audit_id:audit.id,state:audit.state,deleted_files:0,deleted_bytes:0,moved_files:0});index.updated_at=at;
    const out=fs.openSync(registry+'.writing','wx');try{fs.writeFileSync(out,JSON.stringify(index));fs.fsyncSync(out);}finally{fs.closeSync(out);}
    if(await hash(registry)!==expected)throw new Error('Concurrent management update; preserve .writing');fs.renameSync(registry+'.writing',registry);
  }
  console.log(JSON.stringify({id:audit.id,state:audit.state,recorded:record,summary:{...summary,groups:undefined},scope:audit.scope,stage_extractions:extractions,content_verified_files:checked.size,reference_sources:references.witnesses.length,reference_hits:references.hits.length,deleted_files:0,index_sha256:await hash(registry)},null,2));
}
if(require.main===module){const [mode,pin,...extra]=process.argv.slice(2);if(!['--read','--record'].includes(mode)||extra.length)throw new Error('Use --read/--record INDEX_SHA256');review(pin,mode==='--record').catch(e=>{console.error('ARTIFACTS_TMP_REVIEW_HOLD: '+e.message);process.exitCode=1;});}
module.exports={entryPath,classification,matchExtraction,summarize};
