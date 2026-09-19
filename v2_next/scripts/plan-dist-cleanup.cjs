// Fixed development-host proposal only. Never deletes or runs a package/product/helper.
'use strict';
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),crypto=require('node:crypto');
const {execFileSync}=require('node:child_process');
const {plain,walk,hash,inside,assertMigrationStates}=require('./manage-verification-files.cjs');
const {stableKey}=require('./review-dist-artifacts.cjs');
const repo=path.resolve(__dirname,'..'),root=path.join(repo,'dist'),registry=path.join(repo,'verification-files.local.json');
const classificationId='3cdfb7ed-2ce7-45c6-983f-c18d2a6c0e9c';
const kind='DESKTOP_DIST_EXACT_DUPLICATE_PLAN';
// 56 matched locations across current sources, legacy helpers, manifests and server records.
// Inspected 2026-09-19; new matches or changed matched-source bytes require a new review.
const reviewedReferenceDigest='17D45B45265BD295322D6B25A6F484CCD69ED8E295433FDBEF52252EE60ACEE9';
const specs=Object.freeze([
  ['SHA256SUMS-master-dd7982e.txt','ci-master-run-29547492889-dd7982e/SHA256SUMS.txt'],
  ['SHA256SUMS-pr174-41bc375.txt','ci-pr174-run-29514782905-41bc375/SHA256SUMS.txt'],
  ['SHA256SUMS-pr174-945e0d8.txt','ci-pr174-run-29516510998-945e0d8/SHA256SUMS.txt'],
  ['SHA256SUMS-v1.0.16.txt','ci-release-v1.0.16-run-29549462968-834ed85/SHA256SUMS.txt'],
  ['smart-factory-logger-v2 Setup 1.0.15-pr174-9FA1543BA7C5.exe','ci-pr174-run-29516510998-945e0d8/smart-factory-logger-v2 Setup 1.0.15.exe'],
  ['smart-factory-logger-v2 Setup 1.0.15-previous-1B29C65E.exe','ci-pr174-run-29514782905-41bc375/smart-factory-logger-v2 Setup 1.0.15.exe'],
  ['smart-factory-logger-v2 Setup 1.0.15.exe','ci-master-run-29547492889-dd7982e/smart-factory-logger-v2 Setup 1.0.15.exe'],
  ['smart-factory-logger-v2 Setup 1.0.16.exe','ci-release-v1.0.16-run-29549462968-834ed85/smart-factory-logger-v2 Setup 1.0.16.exe'],
  ['smart-factory-logger-v2.Setup.1.0.16.exe','ci-release-v1.0.16-run-29549462968-834ed85/smart-factory-logger-v2 Setup 1.0.16.exe']
].map(([relative,keeper])=>Object.freeze({relative,keeper})));
const digest=bytes=>crypto.createHash('sha256').update(bytes).digest('hex').toUpperCase();
const slash=p=>p.replaceAll('\\','/');
function child(base,relative){
  if(typeof relative!=='string'||!relative||/[\\:\x00-\x1f]/.test(relative)||relative.split('/').some(s=>!s||s==='.'||s==='..'))throw new Error('Noncanonical relative path');
  const p=path.resolve(base,...relative.split('/'));if(!inside(p,base))throw new Error('Path outside boundary');return p;
}
function choose(records){
  return specs.map(s=>{
    const r=records.find(f=>f.relative===s.relative);
    if(!r||r.path!==child(root,s.relative)||r.decision!=='CANDIDATE_EXACT_DUPLICATE_REQUIRES_REFERENCE_REVIEW'||r.retained_copy?.path!==child(root,s.keeper)||r.retained_copy.bytes!==r.bytes||r.retained_copy.sha256!==r.sha256)throw new Error('Fixed duplicate/keeper mapping changed');
    return {...r,reason:'EXACT_BYTES_RETAINED_IN_COMPLETE_CI_RELEASE_SET'};
  });
}
function preserveReason(relative){
  if(relative.startsWith('canary_field_kit_inspection_20260807/'))return 'KEEP_LEGACY_PINNED_KIT_AS_A_WHOLE_NOT_SCATTERED_MEMBER_COPIES';
  if(relative.startsWith('spot-tcp-canary-bfd9be7/'))return 'KEEP_COLLECTOR_REQUIRED_BY_SIBLING_PSSCRIPTROOT_REFERENCE';
  if(relative.startsWith('spot-temperature-v25-qa.zip'))return 'KEEP_DOCUMENTED_QA_OUTPUT_AND_ITS_SIDECAR';
  return 'KEEP_MANIFEST_BOUND_RECOVERY_EVIDENCE_AND_DEPENDENCIES_TOGETHER';
}
function parseSums(text){
  const lines=text.trim().split(/\r?\n/),seen=new Set();
  return lines.map(line=>{
    const m=/^([a-fA-F0-9]{64}) [ *]([^\\/:]+)$/.exec(line);
    if(!m||m[2]==='.'||m[2]==='..'||seen.has(m[2].toLowerCase()))throw new Error('Unexpected CI checksum manifest');
    seen.add(m[2].toLowerCase());return {name:m[2],sha256:m[1].toUpperCase()};
  });
}
function inventory(){
  plain(root);const t=walk(root);if(t.links.length||t.errors.length)throw new Error('Incomplete dist boundary');
  return t.files.map(f=>({path:f.path,bytes:f.bytes,snapshot:stableKey(fs.lstatSync(f.path,{bigint:true}))})).sort((a,b)=>a.path.localeCompare(b.path));
}
function sources(audit){
  const files=new Set(audit.static_references.witnesses.map(w=>path.resolve(repo,'..',w.source)));
  const exclusions=/(?:^|\/)(?:_internal|node_modules|frontend_dist)(?:\/|$)|\/frontend\/dist\//i;
  const text=/\.(?:ps1|psm1|cmd|bat|cjs|js|ts|tsx|py|md|json|txt|ya?ml|sh|spec)$/i;
  const git=execFileSync('git',['--no-optional-locks','-c','core.fsmonitor=false','ls-files','-z'],{cwd:repo,encoding:'utf8',windowsHide:true,maxBuffer:20e6});
  for(const f of git.split('\0').filter(Boolean))if(text.test(f)&&!exclusions.test(slash(f)))files.add(path.resolve(repo,f));
  for(const r of audit.files)if(text.test(r.path)&&!/^win-unpacked\/|^SmartFactory_Portable\//.test(r.relative))files.add(r.path);
  const t=walk(path.join(repo,'artifacts','server-evidence'));
  if(t.links.length||t.errors.length)throw new Error('Canonical evidence reference tree incomplete');
  for(const f of t.files)if(text.test(f.path)&&!exclusions.test(slash(f.path)))files.add(f.path);
  return [...files].filter(f=>!/[\\/]plan-dist-cleanup(?:\.test)?\.cjs$/.test(f)).sort();
}
function references(audit){
  const witnesses=[],hits=[],skipped=[];
  for(const file of sources(audit)){
    plain(file);const before=stableKey(fs.lstatSync(file,{bigint:true}));
    if(fs.statSync(file).size>50e6){skipped.push({source:slash(path.relative(repo,file)),reason:'OVER_50MB_NOT_SCANNED'});continue;}
    const bytes=fs.readFileSync(file);
    if(before!==stableKey(fs.lstatSync(file,{bigint:true})))throw new Error('Reference source changed');
    const source=slash(path.relative(repo,file));witnesses.push({source,sha256:digest(bytes),snapshot:before});
    bytes.toString('utf8').split(/\r?\n/).forEach((line,i)=>{
      for(const s of specs)if(line.toLowerCase().includes(s.relative.toLowerCase()))hits.push({source,line:i+1,candidate:s.relative});
    });
  }
  // Only matched-source hashes enter the manual review pin; all other sources are still witnessed.
  const matched=new Set(hits.map(h=>h.source));
  const reviewedSet={hits,witnesses:witnesses.filter(w=>matched.has(w.source)).map(({snapshot,...w})=>w)};
  return {witnesses,hits,skipped,review_digest:digest(JSON.stringify(reviewedSet))};
}
// Constant script receives only a checked, narrow manifest through stdin. No shell interpolation.
const metadataCode=String.raw`
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if($PSVersionTable.PSVersion.Major-lt 7){throw 'PowerShell 7 required'}
$request=[Console]::In.ReadToEnd()|ConvertFrom-Json
$trusted=@('S-1-5-18','S-1-5-32-544',[Security.Principal.WindowsIdentity]::GetCurrent().User.Value)
$identities=@{}
$records=foreach($r in $request){
    $node=[IO.FileInfo]::new($r.path)
    while($null-ne$node){
        if(($node.Attributes-band[IO.FileAttributes]::ReparsePoint)-ne 0){throw 'Reparse path'}
        if($node-is[IO.FileInfo]){$node=$node.Directory}else{$node=$node.Parent}
    }
    $item=Get-Item -LiteralPath $r.path -Force
    $acl=Get-Acl -LiteralPath $r.path
    $parentAcl=Get-Acl -LiteralPath $item.DirectoryName
    $outside=@(foreach($dacl in @($acl,$parentAcl)){
        foreach($rule in $dacl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier])){
            if($rule.AccessControlType-eq'Allow'-and($rule.PropagationFlags-band[Security.AccessControl.PropagationFlags]::InheritOnly)-eq 0-and$rule.IdentityReference.Value-cnotin$trusted-and([int]$rule.FileSystemRights-band 0xD0156)-ne 0){$rule.IdentityReference.Value}
        }
    })
    $outside=@($outside|Sort-Object -Unique)
    foreach($sid in $outside){
        if(-not$identities.ContainsKey($sid)){
            $account=$null
            try{$account=[Security.Principal.SecurityIdentifier]::new($sid).Translate([Security.Principal.NTAccount]).Value}catch [Security.Principal.IdentityNotMappedException]{}
            $identities[$sid]=[pscustomobject]@{sid=$sid;account=$account;resolved=($null-ne$account)}
        }
    }
    $streams=@(Get-Item -LiteralPath $r.path -Stream '*'|Where-Object Stream -ne ':$DATA')
    $held=[IO.File]::Open($r.path,'Open','Read','None')
    $sha=[Security.Cryptography.SHA256]::Create()
    try{
        $actual=[BitConverter]::ToString($sha.ComputeHash($held)).Replace('-','')
        if($held.Length-ne$r.bytes-or$actual-cne$r.sha256){throw 'Content changed during exclusive read'}
    }finally{$sha.Dispose();$held.Dispose()}
    [pscustomobject]@{
        path=$r.path;bytes=$item.Length;sha256=$actual;exclusive_read_pass=$true
        attributes=[int]$item.Attributes;sddl=$acl.Sddl;parent_sddl=$parentAcl.Sddl
        owner_trusted=($acl.GetOwner([Security.Principal.SecurityIdentifier]).Value-cin$trusted)
        parent_owner_trusted=($parentAcl.GetOwner([Security.Principal.SecurityIdentifier]).Value-cin$trusted)
        outside_writer_sids=$outside;named_stream_count=$streams.Count
        outside_writer_identities=@(foreach($sid in $outside){$identities[$sid]})
        creation_utc_ticks=$item.CreationTimeUtc.Ticks.ToString();last_write_utc_ticks=$item.LastWriteTimeUtc.Ticks.ToString()
    }
}
ConvertTo-Json -InputObject @($records) -Depth 6 -Compress
`;
function metadataHolds(records){
  return records.flatMap(r=>{
    const reasons=[];
    if(!r.exclusive_read_pass)reasons.push('EXCLUSIVE_READ_FAILED');
    if(!r.owner_trusted||!r.parent_owner_trusted)reasons.push('OWNER_TRUST_UNRESOLVED');
    if(r.outside_writer_sids.length)reasons.push('FILE_OR_PARENT_WRITER_TRUST_UNRESOLVED');
    if(r.named_stream_count)reasons.push('ALTERNATE_STREAMS');
    if(r.attributes&1)reasons.push('READONLY_ATTRIBUTE');
    return reasons.length?[{path:r.path,reasons}]:[];
  });
}
async function plan({expected,record=false}){
  if(process.platform!=='win32'||os.hostname()!=='DESKTOP-SS5CURC')throw new Error('Development host mismatch');
  plain(registry);const original=await hash(registry);
  if(!/^[A-F0-9]{64}$/.test(expected||'')||original!==expected)throw new Error('Registry SHA256 differs');
  const index=JSON.parse(fs.readFileSync(registry,'utf8'));assertMigrationStates(index);
  if(index.host!==os.hostname()||index.workspace!==repo||index.plans.some(p=>p.state!=='COMPLETE')||index.migrations.some(m=>m.state!=='COMPLETE'))throw new Error('Incomplete management state');
  if(index.audits.some(a=>a.kind===kind))throw new Error('A dist proposal already exists; inspect it, do not overwrite or repeat');
  const previous=index.audits.find(a=>a.id===classificationId);
  if(previous?.state!=='CLASSIFIED_NOT_APPROVED_FOR_DELETION'||previous.root!==root||previous.deletion_authorized!==false)throw new Error('Prior classification differs');
  const candidates=previous.files.filter(r=>r.decision.startsWith('CANDIDATE_')),remove=choose(candidates);
  if(candidates.length!==35||remove.length!==9)throw new Error('Candidate count differs');
  const tracked=new Set(execFileSync('git',['--no-optional-locks','-c','core.fsmonitor=false','ls-files','-z'],{cwd:repo,encoding:'utf8',windowsHide:true,maxBuffer:20e6}).split('\0').filter(Boolean).map(p=>path.resolve(repo,p).toLowerCase()));
  if(remove.some(r=>tracked.has(r.path.toLowerCase())))throw new Error('A proposed file is now tracked');
  const before=inventory(),old=previous.files.map(({path,bytes,snapshot})=>({path,bytes,snapshot})).sort((a,b)=>a.path.localeCompare(b.path));
  if(JSON.stringify(before)!==JSON.stringify(old))throw new Error('dist changed since classification');
  console.log('[1/4] Verify all 35 candidate/copy pairs and the four retained complete CI sets.');
  const checked=new Map();
  async function check(r){
    const prior=checked.get(r.path);if(prior){if(prior.sha256!==r.sha256||prior.bytes!==r.bytes)throw new Error('Conflicting content pins');return prior;}
    plain(r.path);const stat=fs.lstatSync(r.path,{bigint:true});
    if(!stat.isFile()||stat.nlink!==1n||Number(stat.size)!==r.bytes||await hash(r.path)!==r.sha256)throw new Error('Content/link mismatch: '+path.basename(r.path));
    const result={path:r.path,bytes:r.bytes,sha256:r.sha256,snapshot:stableKey(stat)};checked.set(r.path,result);return result;
  }
  for(const r of candidates){await check(r);await check(r.retained_copy);}
  const ciSets=[];
  for(const name of [...new Set(specs.map(s=>s.keeper.split('/')[0]))]){
    const base=child(root,name),members=previous.files.filter(r=>r.relative.startsWith(name+'/'));
    if(members.length!==3||members.some(r=>r.decision!=='KEEP_COMPLETE_CI_RELEASE_SET')||fs.readdirSync(base).length!==3)throw new Error('Incomplete retained CI set');
    for(const r of members)await check(r);
    const sums=parseSums(fs.readFileSync(path.join(base,'SHA256SUMS.txt'),'utf8'));
    if(sums.length!==2||sums.some(s=>!members.some(m=>m.path===child(base,s.name)&&m.sha256===s.sha256)))throw new Error('CI manifest/content differs');
    ciSets.push({root:base,files:members.map(m=>checked.get(m.path))});
  }
  console.log('[2/4] Read expanded source/archive reference names; record hashes, not contents.');
  const staticInfo=references(previous);
  console.log('[3/4] Read live references, ACLs, alternate streams and exclusive-open checks. No mutation.');
  const usage=JSON.parse(execFileSync('pwsh.exe',['-NoLogo','-NoProfile','-File',path.join(__dirname,'read-dist-use.ps1')],{cwd:repo,encoding:'utf8',windowsHide:true,timeout:90000,maxBuffer:2e6}));
  const narrow=[...new Set(remove.flatMap(r=>[r.path,r.retained_copy.path]))].map(p=>checked.get(p));
  const metadata=JSON.parse(execFileSync('pwsh.exe',['-NoLogo','-NoProfile','-NonInteractive','-Command',metadataCode],{input:JSON.stringify(narrow),encoding:'utf8',windowsHide:true,timeout:90000,maxBuffer:2e6}));
  if(metadata.length!==narrow.length||narrow.some(r=>!metadata.some(m=>m.path===r.path&&m.bytes===r.bytes&&m.sha256===r.sha256)))throw new Error('Metadata set mismatch');
  console.log('[4/4] Recheck witnesses; append proposal only, never a deletion authorization.');
  if(JSON.stringify(inventory())!==JSON.stringify(before))throw new Error('dist changed during proposal');
  for(const r of checked.values())if(stableKey(fs.lstatSync(r.path,{bigint:true}))!==r.snapshot)throw new Error('Candidate/copy changed');
  for(const w of staticInfo.witnesses)if(stableKey(fs.lstatSync(path.resolve(repo,w.source),{bigint:true}))!==w.snapshot)throw new Error('Source changed during proposal');
  if(JSON.stringify(sources(previous))!==JSON.stringify(staticInfo.witnesses.map(w=>path.resolve(repo,w.source))))throw new Error('Reference source membership changed or coverage incomplete');
  const holds=metadataHolds(metadata);
  if(usage.matches.length)holds.push('OBSERVED_DIST_RUNTIME_REFERENCE');
  if(staticInfo.review_digest!==reviewedReferenceDigest)holds.push('REFERENCE_SET_REQUIRES_MANUAL_REVIEW');
  if(staticInfo.skipped.length)holds.push('REFERENCE_FILES_EXCEED_BOUNDED_READER');
  const id=crypto.randomUUID(),at=new Date().toISOString();
  const audit={id,kind,at,classification_id:classificationId,original_registry_sha256:original,root,state:holds.length?'PLAN_REVIEW_HOLD':'PLAN_COMPLETE_AWAITING_APPROVAL',
    files:remove.map(r=>({...checked.get(r.path),relative:r.relative,retained_copy:checked.get(r.retained_copy.path),reason:r.reason})),
    preserved_candidates:candidates.filter(r=>!remove.some(x=>x.path===r.path)).map(r=>({path:r.path,bytes:r.bytes,sha256:r.sha256,reason:preserveReason(r.relative)})),
    retained_ci_sets:ciSets,static_references:staticInfo,usage,metadata,holds,
    counts:{proposed_files:remove.length,proposed_bytes:remove.reduce((n,r)=>n+r.bytes,0),preserved_candidates:26,preserved_candidate_bytes:candidates.filter(r=>!remove.some(x=>x.path===r.path)).reduce((n,r)=>n+r.bytes,0),rehash_verified_paths:checked.size},
    reference_resolution:[
      'Root checksum duplicates and installer aliases map to identical bytes in complete retained CI sets. CI manifests remain beside their original members.',
      'The root-cause report mentions the historical rollback filename, not a live dist root invocation. Preserve the report and exact rollback bytes; record the old path/copy mapping, do not edit historical evidence.',
      'Archived server helpers resolve rollback paths under Desktop/SmartFactory or its recovery/dependencies directory, not this development dist root. Their helpers, manifests and recovery trees remain intact.',
      'The old spot-tcp field guide refers to its kit installer (a different pinned hash); it is not evidence that this root duplicate is the kit dependency. No kit member is removed.',
      'Current workflow wildcard distribution output is a build-time producer/selector, not permission to run these old installers. Complete CI sets, win-unpacked and SmartFactory_Portable remain untouched.',
      'QA ZIP and sidecar remain at the documented output path. All 26 kit/recovery/QA candidates stay; scattered same-byte copies do not justify breaking these bundles.'
    ],
    deletion_authorized:false,deletion_ready:false,deleted_files:0,deleted_bytes:0,moved_files:0,acl_writes:0,remote_server_operations:0,
    predelete_requirements:['User approval of these exact nine paths and byte-identical keeper mappings.','Fresh content/metadata, file and ancestor ACL/reparse/ADS, exclusive-open and observable reference checks.','Keep all CI members and all remaining dist files; no directory removal, wildcard removal, automatic retry or ACL repair.','Durable per-file deletion journal in this registry and post-delete absent/keeper checks.'],
    recovery:'Restore the original filename bytes from its directly mapped retained CI member only with separate restoration approval. Not a promise of automatic restoration or installer operational suitability.',
    limitations:['Read-only live checks are not an atomic snapshot. Handles are released; later deletion must recheck.','Unreadable process metadata, relative/dynamic paths, shell working directories and external scripts are not exhaustively visible.','Source search excludes large bundled dependencies and archive interiors. It is local reference review, not proof of global non-use.','Default-stream byte copies do not imply that file timestamps/ACLs or installed behavior are interchangeable. Original metadata is recorded, no runtime acceptance is asserted.']};
  audit.tooling=await Promise.all(['plan-dist-cleanup.cjs','plan-dist-cleanup.test.cjs','read-dist-use.ps1'].map(async p=>({source:p,sha256:await hash(path.join(__dirname,p))})));
  if(await hash(registry)!==original)throw new Error('Concurrent registry update');
  if(record){
    // An ACL/use HOLD is a result to preserve, not a reason to omit the audit.
    // Unreviewed references, however, must never be published as a finalized proposal.
    if(staticInfo.review_digest!==reviewedReferenceDigest||staticInfo.skipped.length)throw new Error('Reference review incomplete; no registry writes');
    index.audits.push(audit);index.history.push({at,kind,audit_id:id,state:audit.state,deleted_files:0,deleted_bytes:0,moved_files:0});index.updated_at=at;
    const fd=fs.openSync(registry+'.writing','wx');try{fs.writeFileSync(fd,JSON.stringify(index));fs.fsyncSync(fd);}finally{fs.closeSync(fd);}
    if(await hash(registry)!==original)throw new Error('Concurrent registry update; preserve staging proposal');
    fs.renameSync(registry+'.writing',registry);
  }
  console.log(JSON.stringify({id,state:audit.state,recorded:record,counts:audit.counts,holds:record?{metadata_files:metadataHolds(metadata).length,observed_usage_references:usage.matches.length}:holds,reference_digest:staticInfo.review_digest,reference_sources:staticInfo.witnesses.length,reference_hits:record?staticInfo.hits.length:staticInfo.hits,reference_skipped:staticInfo.skipped,usage,metadata_records:metadata.length,deleted_files:0,registry_sha256:record?await hash(registry):original},null,2));
  return audit;
}
if(require.main===module){
  const [mode,expected,...extra]=process.argv.slice(2);
  if(!['--read','--record'].includes(mode)||extra.length){console.error('Use --read or --record followed by the current external registry SHA256');process.exitCode=1;}
  else plan({record:mode==='--record',expected}).catch(e=>{console.error('DIST_PLAN_HOLD: '+e.message);process.exitCode=1;});
}
module.exports={specs,child,choose,preserveReason,parseSums,metadataCode,metadataHolds,references};
