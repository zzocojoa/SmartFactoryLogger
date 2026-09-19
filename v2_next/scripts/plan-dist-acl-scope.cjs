// Read-only ACL scope review. Only the existing management registry can be updated.
'use strict';
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),crypto=require('node:crypto');
const {execFileSync}=require('node:child_process');
const {plain,walk,hash,assertMigrationStates}=require('./manage-verification-files.cjs');
const {stableKey}=require('./review-dist-artifacts.cjs');
const {metadataCode}=require('./plan-dist-cleanup.cjs');
const repo=path.resolve(__dirname,'..'),registry=path.join(repo,'verification-files.local.json');
const reviewId='45788395-d10c-4a97-a04c-1049f635942c',kind='DESKTOP_DIST_ACL_SCOPE_REVIEW';
const ops='C:\\ProgramData\\SFLOps';
const archive=path.join(ops,'releases','legacy-ci','dist-'+reviewId);
const sha=bytes=>crypto.createHash('sha256').update(bytes).digest('hex').toUpperCase();
function proposal(review){
  if(review.id!==reviewId||review.files.length!==9||review.retained_ci_sets.length!==4)throw new Error('Fixed prior review differs');
  const groups=review.retained_ci_sets.map(g=>({source:g.root,destination:path.join(archive,path.basename(g.root)),files:g.files.map(f=>({...f,destination:path.join(archive,path.basename(g.root),path.basename(f.path))}))}));
  const files=groups.flatMap(g=>g.files),bytes=files.reduce((n,f)=>n+f.bytes,0);
  if(files.length!==12||new Set(files.map(f=>f.destination.toLowerCase())).size!==12||files.some(f=>path.dirname(f.path)!==groups.find(g=>f.path.startsWith(g.source+path.sep))?.source))throw new Error('CI member topology differs');
  const directories=[ops,path.join(ops,'releases'),path.join(ops,'releases','legacy-ci'),archive,...groups.map(g=>g.destination)];
  if(files.some(f=>f.destination.length>240))throw new Error('Proposed path exceeds the server tooling budget');
  const duplicateBytes=review.files.reduce((n,f)=>n+f.bytes,0);
  return {option:'NEW_PROTECTED_ARCHIVE_INSTEAD_OF_EXISTING_ACL_REPAIR',destination_host:'DESKTOP-SS5CURC',archive_root:archive,groups,new_directories:directories,
    new_directory_access:'Protected DACL, owner Administrators; SYSTEM and Administrators FullControl only. Atomic secure creation, no reuse of existing paths without a new review.',
    existing_acl_changes:[],existing_owner_group_changes:[],copy_files:12,copy_bytes:bytes,max_destination_path_chars:Math.max(...files.map(f=>f.destination.length)),
    eventual_original_ci_removal_files:files.map(f=>({path:f.path,bytes:f.bytes,sha256:f.sha256})),existing_duplicate_proposal:review.files.map(f=>({path:f.path,bytes:f.bytes,sha256:f.sha256})),
    copy_only_net_logical_bytes_freed:-bytes,copy_then_only_nine_duplicates_net_logical_bytes_freed:duplicateBytes-bytes,
    complete_migration_and_nine_duplicates_net_logical_bytes_freed:duplicateBytes,
    migration_authorized:false,acl_change_authorized:false,deletion_authorized:false,execution_ready:false,
    approval_scope:'This is an alternative requiring a new user decision, not approval inferred from the ACL-plan request. Source removal expands from nine duplicates to twelve migrated CI originals plus the nine duplicates.',
    preconditions:['Administrator execution on the development PC; no remote server access.','Fresh path/ancestor ACL, reparse, ADS, link, source hash, capacity and usage checks. Create each directory with its restrictive ACL in the creation operation.','Copy and verify all twelve CI members and four checksum manifests before any original is removed. Leave all sources on a copy/check failure.','Update management path mappings and a protected execution receipt only after verification. Keep historical documents/helpers unchanged.','A deletion implementation must bind file/directory handles and identities through its commit, or independently satisfy the parent/leaf trust boundary. A protected backup alone does not authorize deleting files from untrusted parents.','Keep global repository and Codex sandbox ACLs unchanged. Do not broadly suppress unresolved SID checks.','Migration/deletion journaling and manager verify support must be implemented and tested before execution.'],
    recovery:'Before source removal, rollback is to retain the original trees and keep the incomplete destination for diagnosis. After approved source removal, restore bytes/path metadata from the protected copy in a separate reviewed operation; no automatic rollback.',
    limitation:'Administrative access is needed for subsequent protected-archive reads. Same-disk storage is not disaster recovery. Peak copy needs about 2.13 GB plus journal/headroom; copying alone increases usage. Logical size is not guaranteed physical disk savings.'};
}
const aclCode=String.raw`
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$paths=[Console]::In.ReadToEnd()|ConvertFrom-Json
$trusted=@('S-1-5-18','S-1-5-32-544',[Security.Principal.WindowsIdentity]::GetCurrent().User.Value)
$rows=foreach($p in $paths){
    if(-not(Test-Path -LiteralPath $p)){[pscustomobject]@{path=$p;exists=$false};continue}
    $item=Get-Item -LiteralPath $p -Force
    if(($item.Attributes-band[IO.FileAttributes]::ReparsePoint)-ne 0){throw 'Reparse boundary'}
    $acl=Get-Acl -LiteralPath $p
    $rules=@(foreach($r in $acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier])){
        [pscustomobject]@{sid=$r.IdentityReference.Value;type=[string]$r.AccessControlType;mask=[int]$r.FileSystemRights;inherited=$r.IsInherited;inheritance=[int]$r.InheritanceFlags;propagation=[int]$r.PropagationFlags}
    })
    $outside=@($rules|Where-Object {$_.type-eq'Allow'-and$_.sid-cnotin$trusted-and($_.propagation-band 2)-eq 0-and($_.mask-band 0xD0156)-ne 0})
    [pscustomobject]@{path=$p;exists=$true;sddl=$acl.Sddl;protected=$acl.AreAccessRulesProtected;owner_sid=$acl.GetOwner([Security.Principal.SecurityIdentifier]).Value;rules=$rules;outside_writers=$outside.Count;outside_delete_child=@($outside|Where-Object {($_.mask-band 0x40)-ne 0}).Count}
}
ConvertTo-Json -InputObject @($rows) -Depth 7 -Compress
`;
function ps(code,input){return JSON.parse(execFileSync('pwsh.exe',['-NoLogo','-NoProfile','-NonInteractive','-Command',code],{input:JSON.stringify(input),encoding:'utf8',windowsHide:true,timeout:60000,maxBuffer:4e6}));}
function inventory(root){plain(root);const t=walk(root);if(t.links.length||t.errors.length)throw new Error('Incomplete dist tree');return t.files.map(f=>({path:f.path,bytes:f.bytes,snapshot:stableKey(fs.lstatSync(f.path,{bigint:true}))})).sort((a,b)=>a.path.localeCompare(b.path));}
async function run(expected,record){
  if(process.platform!=='win32'||os.hostname()!=='DESKTOP-SS5CURC')throw new Error('Wrong development host');
  plain(registry);const original=await hash(registry);
  if(!/^[A-F0-9]{64}$/.test(expected||'')||original!==expected)throw new Error('External registry SHA256 differs');
  const index=JSON.parse(fs.readFileSync(registry,'utf8'));assertMigrationStates(index);
  if(index.host!==os.hostname()||index.workspace!==repo||index.plans.some(p=>p.state!=='COMPLETE')||index.migrations.some(m=>m.state!=='COMPLETE'))throw new Error('Unfinished or mismatched management state');
  if(index.audits.some(a=>a.kind===kind))throw new Error('Scope review already exists; do not overwrite it');
  const prior=index.audits.find(a=>a.id===reviewId);
  if(prior?.state!=='PLAN_REVIEW_HOLD'||prior.deletion_authorized!==false||prior.cleanup)throw new Error('Prior HOLD state differs');
  const suggestion=proposal(prior),root=prior.root,before=inventory(root);
  const pins=[...new Map([...prior.files,...prior.retained_ci_sets.flatMap(g=>g.files)].map(f=>[f.path,f])).values()];
  console.log('[1/3] Rehash nine duplicates and twelve complete CI members; inspect ACLs without changes.');
  for(const f of pins){plain(f.path);const s=fs.lstatSync(f.path,{bigint:true});if(!s.isFile()||s.nlink!==1n||Number(s.size)!==f.bytes||await hash(f.path)!==f.sha256)throw new Error('Source identity drift');}
  const metadata=ps(metadataCode,pins.map(({path,bytes,sha256})=>({path,bytes,sha256})));
  if(metadata.length!==21||metadata.some(m=>!m.exclusive_read_pass||m.named_stream_count))throw new Error('Exclusive/stream evidence differs');
  const ancestors=[];let next=root;while(next){ancestors.push(next);const parent=path.dirname(next);if(parent===next)break;next=parent;}
  const boundaries=[...new Set([...ancestors,...prior.retained_ci_sets.map(g=>g.root),'C:\\ProgramData',...suggestion.new_directories])];
  const aclBefore=ps(aclCode,boundaries);
  if(suggestion.new_directories.some(p=>aclBefore.find(r=>r.path===p)?.exists))throw new Error('Proposed destination already exists; no automatic reuse');
  console.log('[2/3] Compare file-only, broad inherited and new-archive scopes; no ACL mutation is selected.');
  const parentFindings=aclBefore.filter(r=>r.exists&&[root,repo,path.dirname(repo)].includes(r.path));
  if(parentFindings.length!==3||parentFindings.some(r=>r.outside_delete_child===0))throw new Error('Parent deletion risk changed; review the recommendation again');
  const ciFileNames=prior.retained_ci_sets.map(g=>({root:g.root,names:fs.readdirSync(g.root).sort()}));
  if(ciFileNames.some(g=>g.names.length!==3))throw new Error('CI set membership differs');
  const audit={id:crypto.randomUUID(),kind,at:new Date().toISOString(),original_registry_sha256:original,plan_id:reviewId,state:'SCOPE_REVIEW_COMPLETE_ALTERNATIVE_NEEDS_DECISION',
    authority:'User approved preparation of a minimal ACL plan only. No ACL write, copy, migration or deletion was approved in this turn.',
    metadata,acl_boundaries:aclBefore,parent_findings:parentFindings,ci_membership:ciFileNames,
    alternatives:[
      {name:'Change only seventeen file ACLs',recommended:false,reason:'Parent DeleteChild remains on dist and both repository levels; leaf-only ACLs are not a complete deletion/rename protection boundary.'},
      {name:'Remove inherited writers across dist/repository',recommended:false,reason:'Would alter shared development/Codex access; protecting existing children also changes their inheritance and does not solve writable higher parents. Do not apply the old four-dependency-root repair here.'},
      {name:'Leave current ACLs and separately migrate four complete CI sets',recommended:true,reason:'Creates a separate archive boundary without changing live build/source permissions. Requires new path/migration approval, administrative tooling and tested deletion race protection.'}
    ],proposal:suggestion,
    documentation:[{url:'https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-deletefilew',claim:'Delete or rename may be authorized by DELETE on the item or delete-child on its parent.'},{url:'https://learn.microsoft.com/en-us/dotnet/api/system.security.accesscontrol.objectsecurity.setaccessruleprotection',claim:'Protected ACLs control inheritance; this is not protection from a separate parent delete-child grant.'}],
    existing_acl_writes:0,new_directories_created:0,copied_files:0,deleted_files:0,deleted_bytes:0,moved_files:0,remote_server_operations:0,
    unmodified_dist_files:before.length,prior_hold_resolved:false,
    limitations:['No adversarial race fixture, physical migration, restore or ACL-write test was executed. This is a plan, not an executable approval.','Unknown SIDs are unresolved identities, not proof of compromise. CodexSandboxUsers was identified; its repository permissions are not removed.','Process/use references must be refreshed before any future operation; no product was started or queried.']};
  audit.tooling=await Promise.all(['plan-dist-acl-scope.cjs','plan-dist-acl-scope.test.cjs','plan-dist-cleanup.cjs'].map(async source=>({source,sha256:await hash(path.join(__dirname,source))})));
  console.log('[3/3] Verify unchanged file membership/metadata and boundary ACLs, then append only the review.');
  if(JSON.stringify(inventory(root))!==JSON.stringify(before)||JSON.stringify(ps(aclCode,boundaries))!==JSON.stringify(aclBefore))throw new Error('Source or ACL changed during review');
  if(await hash(registry)!==original)throw new Error('Concurrent registry update');
  if(record){
    index.audits.push(audit);index.history.push({at:audit.at,kind,audit_id:audit.id,state:audit.state,acl_writes:0,deleted_files:0,deleted_bytes:0,moved_files:0});index.updated_at=audit.at;
    const fd=fs.openSync(registry+'.writing','wx');try{fs.writeFileSync(fd,JSON.stringify(index));fs.fsyncSync(fd);}finally{fs.closeSync(fd);}
    if(await hash(registry)!==original)throw new Error('Concurrent index update; preserve staging record');
    fs.renameSync(registry+'.writing',registry);
  }
  console.log(JSON.stringify({id:audit.id,state:audit.state,recorded:record,metadata_files:metadata.length,acl_boundaries:aclBefore.length,parent_findings:parentFindings.map(({path,outside_writers,outside_delete_child})=>({path,outside_writers,outside_delete_child})),proposal:{archive_root:suggestion.archive_root,copy_files:suggestion.copy_files,copy_bytes:suggestion.copy_bytes,new_directories:suggestion.new_directories.length,max_path_chars:suggestion.max_destination_path_chars,net_logical_bytes_after_full_migration_and_cleanup:suggestion.complete_migration_and_nine_duplicates_net_logical_bytes_freed},acl_writes:0,deleted_files:0,index_sha256:record?await hash(registry):original},null,2));
}
if(require.main===module){const [mode,expected,...extra]=process.argv.slice(2);if(!['--read','--record'].includes(mode)||extra.length){console.error('Use --read or --record and the current registry SHA256');process.exitCode=1;}else run(expected,mode==='--record').catch(e=>{console.error('DIST_ACL_SCOPE_HOLD: '+e.message);process.exitCode=1;});}
module.exports={proposal,aclCode,reviewId};
