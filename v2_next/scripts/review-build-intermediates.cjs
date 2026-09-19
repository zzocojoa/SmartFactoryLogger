'use strict';
// Read-only payload preflight; --record appends one audit to the existing manager.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),os=require('node:os');
const {execFileSync}=require('node:child_process');
const {plain,walk,hash,inside,assertMigrationStates}=require('./manage-verification-files.cjs');
const {stableKey}=require('./review-dist-artifacts.cjs');
const {topLevelSpans}=require('./finalize-verification-retention.cjs');
const repo=path.resolve(__dirname,'..'),registry=path.join(repo,'verification-files.local.json');
const kind='DESKTOP_BUILD_INTERMEDIATE_USE_REVIEW';
const digest=b=>crypto.createHash('sha256').update(b).digest('hex').toUpperCase();
const rel=p=>path.relative(repo,p).replaceAll('\\','/');
const roots=['backend/build/SmartFactoryBackend','backend/build/spot-temperature-v25-qa/work/validate_csv_v2_shadow'];
function decision(name){
  if(name.includes('\\')||name.split('/').some(s=>s==='..'||s==='.')||name.includes(':'))throw Error('Noncanonical intermediate name');
  const root=roots.find(r=>name.startsWith(r+'/'));if(!root)throw Error('Outside reviewed units');
  const leaf=name.slice(root.length+1);
  if(/^(Analysis|COLLECT|EXE|PKG|PYZ)-00\.toc$/.test(leaf)||/^warn-[^/]+\.txt$|^xref-[^/]+\.html$/.test(leaf))return 'KEEP_BUILD_DIAGNOSTICS';
  const allowed=['PYZ-00.pyz','base_library.zip','localpycs/struct.pyc','localpycs/pyimod04_pywin32.pyc','localpycs/pyimod03_ctypes.pyc','localpycs/pyimod02_importers.pyc','localpycs/pyimod01_archive.pyc',root===roots[0]?'SmartFactoryBackend.pkg':'validate_csv_v2_shadow.pkg'];
  if(root===roots[0])allowed.push('SmartFactoryBackend.exe');
  if(!allowed.includes(leaf))throw Error('Unknown build member');
  return 'DELETE_CANDIDATE_NOT_AUTHORIZED';
}
function appendReview(raw,audit){
  const spans=topLevelSpans(raw),edits=[];
  const history={at:audit.at,kind:audit.kind,audit_id:audit.id,state:audit.state,deleted_files:0,moved_files:0};
  for(const [key,item] of [['audits',audit],['history',history]]){
    const span=spans.get(key);if(!span||raw[span.start]!=='[')throw Error('Missing audit/history');
    edits.push({start:span.end-1,end:span.end-1,text:(raw.slice(span.start+1,span.end-1).trim()?',':'')+JSON.stringify(item)});
  }
  edits.push({...spans.get('updated_at'),text:JSON.stringify(audit.at)});
  let output=raw;for(const e of edits.sort((a,b)=>b.start-a.start))output=output.slice(0,e.start)+e.text+output.slice(e.end);
  JSON.parse(output);return output;
}
function referenceRole(source){
  if(['scripts/deploy.ps1','scripts/build_spot_temperature_v25_qa_bundle.ps1','docs/nsis-installer-build-prompt.md'].includes(source))return 'BUILD_PRODUCER_OR_BUILD_INSTRUCTION';
  if(/^scripts\/(?:read-build-intermediate-use\.ps1|review-build-intermediates(?:\.test)?\.cjs|finalize-verification-retention(?:\.test)?\.cjs|manage-verification-files(?:\.test)?\.cjs|review-build-cache(?:\.test)?\.ps1)$/.test(source))return 'MANAGEMENT_MAPPING_NOT_PRODUCT_CONSUMER';
  return 'REQUIRES_REFERENCE_REVIEW';
}
async function review(expected,record){
  if(process.platform!=='win32'||os.hostname()!=='DESKTOP-SS5CURC'||!/^[A-F0-9]{64}$/.test(expected||''))throw Error('Fixed development host/hash required');
  plain(registry);const raw=fs.readFileSync(registry,'utf8');if(digest(raw)!==expected)throw Error('Management hash changed');
  const index=JSON.parse(raw);assertMigrationStates(index);
  if(index.workspace!==repo||index.host!==os.hostname()||index.plans.some(p=>p.state!=='COMPLETE')||index.migrations.some(m=>m.state!=='COMPLETE')||index.audits.some(a=>a.kind===kind))throw Error('Index scope/pending state differs');
  const previous=index.audits.find(a=>a.id==='fd82da0e-aba2-4c9f-9ad4-c21b8f260c8e');
  const selected=previous.files.filter(f=>f.decision==='REVIEW_CANDIDATE');
  if(selected.length!==26||selected.reduce((n,f)=>n+f.bytes,0)!==37535430)throw Error('Preceding selection differs');
  const records=[];for(const f of selected){plain(f.path);if(stableKey(fs.lstatSync(f.path,{bigint:true}))!==f.snapshot||await hash(f.path)!==f.sha256)throw Error('Candidate changed');records.push({...f,decision:decision(f.relative),deletion_authorized:false});}
  const candidates=records.filter(f=>f.decision==='DELETE_CANDIDATE_NOT_AUTHORIZED');
  if(candidates.length!==17||candidates.reduce((n,f)=>n+f.bytes,0)!==36648177)throw Error('Refined count differs');
  console.log('[1/4] Read current source consumers and preserve the nine TOC build-history records.');
  const sources=new Set(['package.json','README.md','AGENTS.md','main.js',...previous.next_review.producer_sources].map(p=>path.resolve(repo,p)));
  for(const base of ['scripts','docs','../.github/workflows']){
    const t=walk(path.resolve(repo,base));if(t.links.length||t.errors.length)throw Error('Source reference scope incomplete');
    for(const f of t.files)if(/\.(ps1|psm1|cjs|mjs|js|py|md|json|ya?ml|cmd|bat)$/i.test(f.path))sources.add(f.path);
  }
  const tracked=execFileSync('git',['--no-optional-locks','-c','core.fsmonitor=false','ls-files','-z'],{cwd:repo,encoding:'utf8',windowsHide:true}).split('\0').filter(Boolean);
  if(records.some(f=>tracked.includes(f.relative)))throw Error('Candidate became tracked');
  for(const p of tracked)if(/^(backend|frontend)\//.test(p)&&/\.(py|spec|js|cjs|mjs|tsx?|json|toml|ini|cfg|ya?ml|ps1|cmd|bat)$/.test(p)&&!/^frontend\/public\//.test(p))sources.add(path.resolve(repo,p));
  const witnesses=[],references=[];
  for(const p of [...sources].sort()){
    plain(p);const stat=fs.lstatSync(p,{bigint:true});if(stat.size>5000000n)throw Error('Source text budget exceeded');
    const b=fs.readFileSync(p),snapshot=stableKey(stat);if(stableKey(fs.lstatSync(p,{bigint:true}))!==snapshot)throw Error('Source changed');
    const source=rel(p);witnesses.push({path:p,sha256:digest(b),snapshot});
    const text=b[0]===255&&b[1]===254?b.subarray(2).toString('utf16le'):b.toString('utf8');
    text.split(/\r?\n/).forEach((line,n)=>{
      const normalized=line.replace(/\\+/g,'/');
      if(/backend\/build(?:\/|[\s"']|$)|build\/(SmartFactoryBackend|spot-temperature-v25-qa)(?:\/|[\s"']|$)/i.test(normalized))references.push({source,line:n+1,role:referenceRole(source)});
    });
  }
  console.log('[2/4] Verify retained backend and QA output manifests without executing either program.');
  const kept=[];
  for(const [directory,manifestName,format] of [['backend/dist/SmartFactoryBackend','bundle-manifest.json','backend'],['dist/spot-temperature-v25-qa','bundle-manifest.json','qa']]){
    const base=path.resolve(repo,directory),manifest=path.join(base,manifestName);plain(manifest);
    const manifestHash=await hash(manifest),m=JSON.parse(fs.readFileSync(manifest,'utf8').replace(/^\uFEFF/,''));
    const members=m.files,seen=new Set();
    if(members.length!==(format==='backend'?1449:6))throw Error('Retained manifest count differs');
    const t=walk(base);if(t.links.length||t.errors.length||t.files.length!==members.length+1)throw Error('Retained output membership differs');
    for(const f of members){
      const name=format==='backend'?f.path:f.name;
      if(typeof name!=='string'||name.includes('\\')||name.split('/').some(s=>!s||s==='.'||s==='..')||name.includes(':')||seen.has(name.toLowerCase()))throw Error('Unsafe manifest member');
      seen.add(name.toLowerCase());const p=path.resolve(base,name);if(!inside(p,base))throw Error('Manifest escape');plain(p);
      const s=fs.lstatSync(p,{bigint:true}),bytes=format==='backend'?f.length:f.size_bytes;
      if(!s.isFile()||s.nlink!==1n||Number(s.size)!==bytes||await hash(p)!==f.sha256.toUpperCase())throw Error('Retained payload hash differs');
      kept.push({path:p,bytes,sha256:f.sha256.toUpperCase(),snapshot:stableKey(s)});
    }
    if(await hash(manifest)!==manifestHash)throw Error('Output manifest changed');
    kept.push({path:manifest,sha256:manifestHash,snapshot:stableKey(fs.lstatSync(manifest,{bigint:true}))});
  }
  console.log('[3/4] Check exclusive read access, file identity/streams/ACLs and observable live registrations.');
  const pwsh='C:\\Users\\user\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\native\\powershell\\pwsh.exe';
  const live=JSON.parse(execFileSync(pwsh,['-NoLogo','-NoProfile','-File',path.join(__dirname,'read-build-intermediate-use.ps1'),'-ExpectedIndexSha256',expected],{cwd:repo,encoding:'utf8',windowsHide:true,timeout:120000,maxBuffer:2000000}));
  if(live.files.length!==31)throw Error('Live unit count differs');
  for(const r of records){const f=live.files.find(f=>f.path===r.path);if(!f||f.sha256!==r.sha256||f.metadata.bytes!==r.bytes)throw Error('Live scope differs');}
  for(const f of [...kept,...witnesses])if(stableKey(fs.lstatSync(f.path,{bigint:true}))!==f.snapshot||await hash(f.path)!==f.sha256)throw Error('Preserved witness changed');
  const unknown=references.filter(r=>r.role==='REQUIRES_REFERENCE_REVIEW'),hold=live.matches.length||unknown.length;
  const audit={id:crypto.randomUUID(),kind,at:new Date().toISOString(),state:hold?'HOLD_REFERENCES_REQUIRE_REVIEW':'REVIEW_COMPLETE_AWAITING_EXACT_DELETE_APPROVAL',source_audit_id:previous.id,original_index_sha256:expected,original_updated_at_token:raw.slice(topLevelSpans(raw).get('updated_at').start,topLevelSpans(raw).get('updated_at').end),
    records,candidate_files:candidates.length,candidate_bytes:36648177,newly_preserved_toc_files:9,preserved_build_files:live.files.filter(f=>!candidates.some(c=>c.path===f.path)),retained_output_files:kept,source_witnesses:witnesses,static_references:references,live_check:live,
    restore_policy:'Keep TOC/spec/warn/xref history and both completed output bundles. A clean build can regenerate intermediates; bit-identical reconstruction of historical intermediate bytes is not guaranteed. No new backup or build is performed.',
    limitations:['Read-only preflight is point-in-time, not permission to delete. Exact membership/hash/ACL/ADS, exclusive-open and live-use checks must be repeated within any separately approved deletion transaction.','Static text scan covers repository scripts/docs/workflows and tracked backend/frontend sources, not every archived or external script; split/dynamic paths are not fully resolvable.','Nine TOC records were previously only candidates; this review preserves them as historical build evidence. Prior audits and original inventory states are not rewritten.'],
    deleted_files:0,deleted_bytes:0,moved_files:0,existing_acl_writes:0,remote_server_operations:0,deletion_authorized:false};
  console.log('[4/4] Preserve the exact list and review evidence in the single management file. No deletion.');
  if(await hash(registry)!==expected)throw Error('Concurrent management update');
  if(record){const output=appendReview(raw,audit),fd=fs.openSync(registry+'.writing','wx');try{fs.writeFileSync(fd,output);fs.fsyncSync(fd);}finally{fs.closeSync(fd);}if(await hash(registry)!==expected)throw Error('Concurrent management update; preserve .writing');fs.renameSync(registry+'.writing',registry);if(await hash(registry)!==digest(output))throw Error('Published audit hash differs');}
  console.log(JSON.stringify({id:audit.id,state:audit.state,recorded:record,candidate_files:17,candidate_bytes:36648177,newly_preserved_toc_files:9,preserved_build_files:audit.preserved_build_files.length,retained_output_files:kept.length,source_witnesses:witnesses.length,static_references:references,live_counts:live.counts,live_matches:live.matches,deleted_files:0,index_sha256:await hash(registry)},null,2));
}
if(require.main===module){const [mode,pin,...rest]=process.argv.slice(2);if(!['--read','--record'].includes(mode)||rest.length)throw Error('Use --read/--record INDEX_SHA256');review(pin,mode==='--record').catch(e=>{console.error('BUILD_REVIEW_HOLD: '+e.message);process.exitCode=1;});}
module.exports={decision,appendReview,referenceRole};
