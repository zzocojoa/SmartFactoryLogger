// Local verification inventory. Never starts the product, follows links, or deletes files.
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const crypto = require('node:crypto');
const { execFileSync } = require('node:child_process');
const repo = path.resolve(__dirname, '..');
const indexPath = path.join(repo, 'verification-files.local.json');
const inside = (p, root) => p.toLowerCase().startsWith(root.toLowerCase() + path.sep);
const same = (a, b) => a.toLowerCase() === b.toLowerCase();
const desktopSource = path.join(os.homedir(),'Desktop','test');
const desktopDestination = path.join(repo,'artifacts','server-evidence','desktop-test');
const transferSource=path.join(os.homedir(),'Desktop','SmartFactory');
const transferDestination=path.join(repo,'artifacts','server-evidence','desktop-smartfactory');
const releaseSource=path.join(os.homedir(),'Desktop','SmartFactoryLogger_Release');
const releaseDestination=path.join(repo,'artifacts','server-evidence','desktop-release');
function transferBatchSpecs() {
  return [
    {revision:1,count:3,zip_sha256:'CDA57FBB307D6E9D90923574AD5468131925243DDA2215D03F8D18E3CEC8FD31'},
    {revision:2,count:3,zip_sha256:'D1977BEA736DBE6F37FAFFD8A528CF087869B7D38C7DFA9CCC488E6DB4AE16AD'},
    {revision:3,count:6,zip_sha256:'EAB09A9F52091FDCEED56C38C5246A223B44EB1E4A1C81D59DF2025E5DE97DDB'}
  ].map(s=>({...s,collection:'transfer-0695a0f-r'+s.revision,kind:'DESKTOP_TRANSFER_0695A0F_R'+s.revision+'_MIGRATION',source_leaf:'SmartFactoryLogger_Transfer_0695a0f_20260806'+(s.revision===1?'':'_R'+s.revision)}));
}
function releaseDestinationName(name) {
  const parts=name.split(path.sep);
  if(parts[0]==='spot_connecttimeout_field_kit_077b6b1c_rebuilt_20260727')parts[0]='kit-077b6b1';
  return parts.join(path.sep);
}
function releaseRetention(files) {
  // Keep complete published release/field-kit sets and loose operator scripts.
  // Extracted/staging duplicates may point only to a same-name, same-byte copy.
  const preserve=f=>!/[\\/]/.test(f.name)||/^(release_|spot_request_budget_|spot_connecttimeout_field_kit_)/.test(f.name);
  const groups=new Map(),keepers=new Map();
  for(const f of files){
    const key=path.basename(f.name).toLowerCase()+'|'+f.bytes+'|'+f.sha256;
    if(!groups.has(key))groups.set(key,[]);groups.get(key).push(f);
  }
  for(const group of groups.values()){
    const fixed=group.filter(preserve);
    const pool=fixed.length?fixed:group;
    const chosen=[...pool].sort((a,b)=>a.name.length-b.name.length||a.name.localeCompare(b.name))[0];
    for(const f of group)keepers.set(f.source,preserve(f)?f:chosen);
  }
  return keepers;
}
function assertMigrationStates(index) {
  if((index.migrations||[]).some(m=>!['PLANNED','COMPLETE'].includes(m.state)))throw new Error('Migration incomplete; preserve both locations and its journal');
  assertReviewedCleanupStates(index);
}
function assertReviewedCleanupStates(index) {
  for(const review of index.audits||[]){
    if(review.kind==='DESKTOP_CHROME_TEST_CACHE_CLEANUP'&&review.state!=='COMPLETE')throw new Error('Chrome cache cleanup pending; preserve index/journal and do not rescan');
    if(review.kind==='DESKTOP_BUILD_INTERMEDIATE_CLEANUP'&&review.state!=='COMPLETE')throw new Error('Build intermediate cleanup pending; preserve index/journal and do not rescan');
    if(review.kind==='DESKTOP_ISOLATED_TEST_CACHE_CLEANUP'&&review.state!=='COMPLETE')throw new Error('Isolated cache cleanup pending; preserve journal/index and do not rescan');
    if(review.kind==='DESKTOP_ATTESTATION_EXTRACTION_CLEANUP'&&review.state!=='COMPLETE')throw new Error('Attestation cleanup pending; preserve journal and index; do not rescan over it');
    if(review.kind==='DESKTOP_STAGE_EXTRACTION_CLEANUP'&&review.state!=='COMPLETE')throw new Error('Stage extraction cleanup pending or interrupted; preserve its journal and management record; do not rescan over it');
    if(review.kind==='DESKTOP_DIST_PROTECTED_CI_MIGRATION'&&review.state!=='COMPLETE')throw new Error('Dist migration pending or interrupted; preserve the protected journal and both locations; do not rescan over it');
    if(review.kind==='DESKTOP_DEPENDENCY_ACL_REPAIR'&&review.state!=='COMPLETE')throw new Error('Dependency ACL repair incomplete; preserve its ACL backup and remaining files');
    if(review.kind==='DESKTOP_BUILDS_CACHE_REVIEW'&&review.cleanup&&review.cleanup.state!=='COMPLETE')throw new Error('Reviewed cache cleanup incomplete; preserve its journal and remaining files');
    if(review.kind==='DESKTOP_BUILDS_DEPENDENCY_CLEANUP_PLAN'&&review.cleanup&&review.cleanup.state!=='COMPLETE')throw new Error('Dependency cleanup incomplete; preserve per-file journal and remaining files');
  }
}
function distArchiveRecords(index) {
  const migrations=(index.audits||[]).filter(a=>a.kind==='DESKTOP_DIST_PROTECTED_CI_MIGRATION');
  if(migrations.length>1)throw new Error('Ambiguous dist migration');
  return migrations.map(a=>{
    const base='C:\\ProgramData\\SFLOps\\releases\\legacy-ci\\dist-45788395-d10c-4a97-a04c-1049f635942c';
    const files=a.plan.groups.flatMap(g=>g.files);
    if(a.state!=='COMPLETE'||a.plan.archive_root!==base||files.length!==12||a.plan.files.length!==21||a.copied_files!==12||a.removed_source_files!==21||a.deleted_files!==9||a.moved_files!==12||!a.completion||files.some(f=>!inside(f.destination,base)))throw new Error('Dist migration completion differs');
    const keepers=new Map(files.map(f=>[f.destination,f]));
    if(keepers.size!==12||a.plan.files.some(f=>!keepers.has(f.keeper)||keepers.get(f.keeper).sha256!==f.sha256||keepers.get(f.keeper).bytes!==f.bytes))throw new Error('Dist archive keeper mapping differs');
    return {audit:a,base,files};
  });
}
function stageExtractionRecords(index) {
  const audits=(index.audits||[]).filter(a=>a.kind==='DESKTOP_STAGE_EXTRACTION_CLEANUP');
  if(audits.length>1)throw new Error('Ambiguous stage extraction cleanup');
  for(const a of audits){
    if(a.state!=='COMPLETE'||a.deleted_files!==64||a.deleted_bytes!==331293866||a.files?.length!==64||a.deleted_directories!==0||a.existing_acl_writes!==0||!a.journal_sha256)throw new Error('Stage extraction completion differs');
    const seen=new Set(),counts=[0,0];let bytes=0;
    for(const f of a.files){
      const n=[4,5].find(n=>inside(f.path,path.join(repo,'.tmp','v26stage-tests-r'+n,'actual-transfer')));
      if(!n||seen.has(f.path.toLowerCase())||path.resolve(f.path)!==f.path||!/^[A-F0-9]{64}$/.test(f.sha256))throw new Error('Stage extraction source differs');
      const relative=path.relative(path.join(repo,'.tmp','v26stage-tests-r'+n,'actual-transfer'),f.path);
      if(f.keeper!==path.join(repo,'artifacts','v1026-server-stage-20260911-r'+(n-3),'transfer-files',relative))throw new Error('Stage keeper revision differs');
      seen.add(f.path.toLowerCase());counts[n-4]++;bytes+=f.bytes;
    }
    if(counts.some(n=>n!==32)||bytes!==331293866)throw new Error('Stage extraction totals differ');
  }
  return audits;
}
function attestationExtractionRecords(index) {
  const audits=(index.audits||[]).filter(a=>a.kind==='DESKTOP_ATTESTATION_EXTRACTION_CLEANUP');
  if(audits.length>1)throw new Error('Ambiguous attestation cleanup');
  const specs=[[1,'verify_extract_attempt2','package_attempt2',12,4963177],[2,'verify_extract','package',18,9881026],[3,'verify_extract','package',24,19655538],[4,'verify_extract','package',30,39123763],[5,'verify_extract','package',36,77984184],[5,'expand_archive_verify','package',36,77984184]]
    .map(([n,source,keeper,count,bytes])=>({source:path.join(repo,'.tmp','internal_extended_running_state_attestation_r'+n,source),keeper:path.join(repo,'.tmp','internal_extended_running_state_attestation_r'+n,keeper),count,bytes}));
  for(const a of audits){
    if(a.state!=='COMPLETE'||a.deleted_files!==156||a.deleted_bytes!==229591872||a.files?.length!==156||a.deleted_directories!==0||a.existing_acl_writes!==0||!/^[A-F0-9]{64}$/.test(a.journal_sha256))throw new Error('Attestation completion differs');
    const seen=new Set(),keepers=new Map(),counts=specs.map(()=>0),sizes=specs.map(()=>0);
    for(const f of a.files){
      const i=specs.findIndex(s=>inside(f.path,s.source));
      if(i<0||seen.has(f.path.toLowerCase())||path.resolve(f.path)!==f.path||!Number.isSafeInteger(f.bytes)||f.bytes<0||!/^[A-F0-9]{64}$/.test(f.sha256))throw new Error('Attestation source differs');
      const relative=path.relative(specs[i].source,f.path);
      if(!relative||/(^|\\)\.\.?($|\\)|[:/]|[ .](\\|$)/.test(relative)||f.keeper!==path.join(specs[i].keeper,relative))throw new Error('Attestation keeper revision differs');
      const old=keepers.get(f.keeper.toLowerCase());
      if(old&&(old.sha256!==f.sha256||old.bytes!==f.bytes))throw new Error('Shared attestation keeper differs');
      seen.add(f.path.toLowerCase());keepers.set(f.keeper.toLowerCase(),f);counts[i]++;sizes[i]+=f.bytes;
    }
    if(keepers.size!==120||specs.some((s,i)=>counts[i]!==s.count||sizes[i]!==s.bytes))throw new Error('Attestation totals differ');
  }
  return audits;
}
function isolatedTestCacheSpecs(){
  const runs=[['isolation','54JQVf'],['isolation','BlDyJT'],['isolation','FC51gr'],['optimization','L6rPQy'],['optimization','phfxUN'],['optimization','tSoLDE'],['optimization','xwjcf4']];
  return runs.flatMap(([group,id])=>['Cache','Code Cache','Dictionaries','GPUCache','DawnGraphiteCache','DawnWebGPUCache']
    .filter(u=>id!=='BlDyJT'||['Cache','Code Cache','Dictionaries'].includes(u)).map(category=>{
      const names=category==='Cache'?['Cache_Data/data_0','Cache_Data/data_1','Cache_Data/data_2','Cache_Data/data_3','Cache_Data/f_000001','Cache_Data/index','No_Vary_Search/journal.baj','No_Vary_Search/snapshot.baf']:category==='Code Cache'?['js/index','js/index-dir/the-real-index','wasm/index','wasm/index-dir/the-real-index']:category==='Dictionaries'?['ko-3-0.bdic']:['data_0','data_1','data_2','data_3','index'];
      return {unit:path.join(repo,'artifacts','operator-emphasis-'+group+'-20260910','run-'+id,'electron-profile',category),category,names,bytes:category==='Cache'?13381488:category==='Code Cache'?144:category==='Dictionaries'?11476456:557424};
    }));
}
function isolatedTestCacheRecords(index){
  const audits=(index.audits||[]).filter(a=>a.kind==='DESKTOP_ISOLATED_TEST_CACHE_CLEANUP');
  if(audits.length>1)throw new Error('Ambiguous isolated cache cleanup');
  const specs=isolatedTestCacheSpecs(),allowed=new Map(specs.flatMap(s=>s.names.map(n=>[path.join(s.unit,...n.split('/')),s])));
  for(const a of audits){
    if(a.state!=='COMPLETE'||a.deleted_files!==181||a.deleted_bytes!==184040248||a.files?.length!==181||a.deleted_directories!==0||a.existing_acl_writes!==0||!/^[A-F0-9]{64}$/.test(a.journal_sha256))throw new Error('Isolated cache completion differs');
    const seen=new Set(),sizes=new Map(),counts=new Map();
    for(const f of a.files){
      const s=allowed.get(f.path);
      if(!s||seen.has(f.path)||path.resolve(f.path)!==f.path||s.unit!==f.unit||s.category!==f.category||!Number.isSafeInteger(f.bytes)||f.bytes<0||!/^[A-F0-9]{64}$/.test(f.sha256))throw new Error('Isolated cache member differs');
      seen.add(f.path);sizes.set(s.unit,(sizes.get(s.unit)||0)+f.bytes);counts.set(s.unit,(counts.get(s.unit)||0)+1);
    }
    if(specs.some(s=>counts.get(s.unit)!==s.names.length||sizes.get(s.unit)!==s.bytes))throw new Error('Whole cache unit differs');
    if(a.preserved_files?.length!==419||new Set(a.preserved_files.map(f=>f.path)).size!==419||a.preserved_files.some(f=>seen.has(f.path)))throw new Error('Cache evidence boundary differs');
  }
  return audits;
}
function chromeTestProfileSpecs(){
  return [['.tmp_chrome_cdp_settings_lazy',1340,127982227,66,22073437],['.tmp_chrome_profile_dashboard_qa_role_a',420,38875766,71,22067409],['.tmp_chrome_profile_dashboard_qa_role_a_2',184,35288341,50,21373680],['.tmp_chrome_profile_dashboard_qa_role_a_cdp',1315,56594689,71,22066977],['.tmp_chrome_profile_dashboard_qa_role_a_cdp_2',1315,56594247,71,22066977],['.tmp_chrome_profile_grafana_lazy_qa',1390,136348598,105,30223500],['.tmp_chrome_profile_grafana_split',1347,130643906,71,24694429],['.tmp_chrome_profile_scene_surface',1503,209899652,71,24421781],['.tmp_chrome_profile_settings_lazy',1313,100686608,66,22073437]]
    .map(([name,files,bytes,deleted_files,deleted_bytes])=>({root:path.join(repo,name),files,bytes,deleted_files,deleted_bytes}));
}
function chromeCacheUnit(relative){
  if(/[:/]|(^|\\)\.\.?($|\\)|[ .](\\|$)/.test(relative))throw new Error('Noncanonical Chrome member');
  for(const unit of ['Default\\Cache','Default\\Code Cache','Default\\GPUCache','Default\\DawnWebGPUCache','Default\\DawnGraphiteCache','ShaderCache','GrShaderCache','GraphiteDawnCache']){
    if(!relative.startsWith(unit+'\\'))continue;
    const leaf=relative.slice(unit.length+1),pattern=unit==='Default\\Cache'?/^(Cache_Data\\(index|data_[0-3]|f_[0-9a-f]{6})|No_Vary_Search\\(journal\.baj|snapshot\.baf))$/:unit==='Default\\Code Cache'?/^(js|wasm)\\(index|index-dir\\the-real-index|[0-9a-f]{16}_[01])$/:/^(index|data_[0-3])$/;
    if(!pattern.test(leaf))throw new Error('Unknown member inside Chrome cache unit');
    return unit;
  }
  return null;
}
function chromeTestCacheRecords(index){
  const audits=(index.audits||[]).filter(a=>a.kind==='DESKTOP_CHROME_TEST_CACHE_CLEANUP'),specs=chromeTestProfileSpecs();
  if(audits.length>1)throw new Error('Ambiguous Chrome cache cleanup');
  for(const a of audits){
    if(a.state!=='COMPLETE'||a.deleted_files!==642||a.deleted_bytes!==211061627||a.files?.length!==642||a.preserved_files?.length!==9485||a.deleted_directories!==0||a.existing_acl_writes!==0||!/^[A-F0-9]{64}$/.test(a.journal_sha256))throw new Error('Chrome cache completion differs');
    const seen=new Set(),totals=specs.map(()=>({gone:0,goneBytes:0,kept:0,keptBytes:0}));
    for(const [records,deleting] of [[a.files,true],[a.preserved_files,false]])for(const f of records){
      const i=specs.findIndex(s=>f.path.startsWith(s.root+path.sep));
      if(i<0||path.resolve(f.path)!==f.path||seen.has(f.path.toLowerCase())||!Number.isSafeInteger(f.bytes)||f.bytes<0||!/^[A-F0-9]{64}$/.test(f.sha256))throw new Error('Chrome profile boundary differs');
      seen.add(f.path.toLowerCase());const unit=chromeCacheUnit(path.relative(specs[i].root,f.path));
      if(deleting){if(!unit||f.unit!==path.join(specs[i].root,unit)||f.disposition!=='DELETE_CACHE')throw new Error('Non-cache deletion rejected');totals[i].gone++;totals[i].goneBytes+=f.bytes;}
      else{if(unit||f.disposition!=='KEEP_PROFILE_STATE')throw new Error('Preservation record differs');totals[i].kept++;totals[i].keptBytes+=f.bytes;}
    }
    if(specs.some((s,i)=>totals[i].gone!==s.deleted_files||totals[i].goneBytes!==s.deleted_bytes||totals[i].kept!==s.files-s.deleted_files||totals[i].keptBytes!==s.bytes-s.deleted_bytes))throw new Error('Per-profile totals differ');
  }
  return audits;
}
function buildIntermediateRecords(index){
  const audits=(index.audits||[]).filter(a=>a.kind==='DESKTOP_BUILD_INTERMEDIATE_CLEANUP');
  if(audits.length>1)throw new Error('Ambiguous build intermediate cleanup');
  const root=path.join(repo,'backend','build');
  for(const a of audits){
    if(a.state!=='COMPLETE'||a.deleted_files!==17||a.deleted_bytes!==36648177||a.files?.length!==17||a.preserved_files?.length!==14||a.deleted_directories!==0||a.existing_acl_writes!==0||!/^[A-F0-9]{64}$/.test(a.journal_sha256))throw new Error('Build intermediate completion differs');
    const seen=new Set();let bytes=0;
    for(const f of a.files){if(!inside(f.path,root)||path.resolve(f.path)!==f.path||seen.has(f.path)||!Number.isSafeInteger(f.bytes)||f.bytes<0||!/^[A-F0-9]{64}$/.test(f.sha256)||/\.(toc|txt|html|spec)$/i.test(f.path))throw new Error('Build deletion record differs');seen.add(f.path);bytes+=f.bytes;}
    if(bytes!==36648177||new Set(a.preserved_files.map(f=>f.path)).size!==14||a.preserved_files.some(f=>seen.has(f.path)||!inside(f.path,root)||!/^[A-F0-9]{64}$/.test(f.sha256)))throw new Error('Build evidence boundary differs');
  }
  return audits;
}
function archiveDuplicateRule(relative) {
  const qa='spot-temperature-v25-qa-extracted-20260728/';
  if(relative.startsWith(qa)&&['apply_spot_temperature_v25_attestation.cmd','apply_spot_temperature_v25_attestation.ps1','bundle-manifest.json','qa_spot_temperature_v25.cmd','qa_spot_temperature_v25.ps1','README.md','validate_csv_v2_shadow.exe'].includes(relative.slice(qa.length)))return {zip:'spot-temperature-v25-qa.zip',entry:relative.slice(qa.length)};
  const nsis='pr171-windows-145/nsis-inspect/contents/resources/';
  const entries={
    'backend/bundle-manifest.json':'SmartFactory_Portable\\bundle-manifest.json',
    'backend/SmartFactoryBackend.exe':'SmartFactory_Portable\\SmartFactoryBackend.exe',
    'frontend/dist/index.html':'SmartFactory_Portable\\frontend\\dist\\index.html',
    'frontend/dist/manifest.json':'SmartFactory_Portable\\frontend\\dist\\manifest.json',
    'frontend/dist/assets/CameraWidget-BJLKDLnR.js':'SmartFactory_Portable\\frontend\\dist\\assets\\CameraWidget-BJLKDLnR.js',
    'qa/measure_nsis_operational_ready.ps1':'SmartFactory_Portable\\_internal\\backend\\scripts\\measure_nsis_operational_ready.ps1'
  };
  if(relative.startsWith(nsis)&&Object.hasOwn(entries,relative.slice(nsis.length)))return {zip:'pr171-windows-145/SmartFactory_v1.0.14_Portable.zip',entry:entries[relative.slice(nsis.length)]};
  return null;
}
function desktopEvidenceRoot(index, sourcePath=desktopSource, destinationPath=desktopDestination) {
  const migrations=(index.migrations||[]).filter(m=>m.kind==='DESKTOP_TEST_MIGRATION');
  if(migrations.length>1)throw new Error('Ambiguous desktop evidence migration');
  if(!migrations.length)return sourcePath;
  const migration=migrations[0];
  if(!same(migration.source,sourcePath)||!same(migration.destination,destinationPath))throw new Error('Unexpected desktop evidence mapping');
  if(migration.state==='COMPLETE')return destinationPath;
  if(migration.state==='PLANNED')return sourcePath;
  throw new Error('Desktop evidence migration incomplete; preserve both locations');
}
function plain(p) {
  const full = path.resolve(p);
  for (let current = full;; current = path.dirname(current)) {
    if (fs.lstatSync(current).isSymbolicLink()) throw new Error('Link boundary: ' + current);
    if (path.dirname(current) === current) break;
  }
  return full;
}
function walk(root) {
  const files = [], dirs = [], links = [], errors = [], stack = [root];
  while (stack.length) {
    const p = stack.pop();
    try {
      const s = fs.lstatSync(p);
      if (s.isSymbolicLink()) { links.push({ path: p, target: fs.readlinkSync(p) }); continue; }
      if (s.isDirectory()) {
        // Nested checkouts are source, not disposable verification output.
        if (fs.existsSync(path.join(p, '.git'))) { errors.push({path:p,code:'SOURCE_CHECKOUT_EXCLUDED'}); continue; }
        dirs.push(p);
        for (const name of fs.readdirSync(p)) stack.push(path.join(p, name));
      } else if (s.isFile()) {
        files.push({ path:p, bytes:s.size, mtime_ms:s.mtimeMs, state:'KEEP_UNIQUE_OR_NOT_YET_CLASSIFIED' });
      } else errors.push({path:p,code:'UNSUPPORTED_TYPE'});
    } catch(e) { errors.push({path:p,code:e.code || e.message}); }
  }
  return { files, dirs, links, errors };
}
async function hash(p) {
  plain(p);
  const before = fs.statSync(p), h = crypto.createHash('sha256');
  for await (const chunk of fs.createReadStream(p)) h.update(chunk);
  const after = fs.statSync(p);
  if (before.size !== after.size || before.mtimeMs !== after.mtimeMs || before.ino !== after.ino) throw new Error('File changed: '+p);
  return h.digest('hex').toUpperCase();
}
function readIndexForUpdate() {
  const index = JSON.parse(fs.readFileSync(indexPath, 'utf8'));
  assertMigrationStates(index);
  return index;
}
function save(index) {
  // Guard publication too; future commands must not bypass interrupted work.
  assertMigrationStates(index);
  plain(path.dirname(indexPath));
  if (fs.existsSync(indexPath)) plain(indexPath);
  const staging = indexPath + '.writing';
  const fd = fs.openSync(staging, 'wx');
  try { fs.writeFileSync(fd, JSON.stringify(index)); fs.fsyncSync(fd); } finally { fs.closeSync(fd); }
  fs.renameSync(staging, indexPath);
}
function source(file, needle, kind, rule) {
  const p = path.join(repo, file), lines = fs.readFileSync(p, 'utf8').split(/\r?\n/);
  const line = lines.findIndex(s => s.includes(needle)) + 1;
  if (!line) throw new Error('Storage logic changed: '+file+' '+needle);
  return {source:file.replaceAll('\\','/'),line,kind,rule};
}
function sourceCatalog() {
  return [
    source('scripts/build-spot-realtime-image-canary-kit.ps1','Join-Path $projectRoot "artifacts"','build_output','repo/artifacts; OutputRoot override supported'),
    source('scripts/server-stage-v1026/build-cold-backup-transfer.ps1',"artifacts\\v1026-cold-backup",'build_output','repo/artifacts/versioned delivery'),
    source('scripts/server-stage-v1026/build-installed-read-v1026.ps1',".tmp\\v1026x1",'required_build_input','repo/.tmp/v1026x1 is a current helper build input; preserve'),
    source('scripts/run_backend_unittest.cjs',"'.tmp_test_appdata'",'synthetic_test_output','repo/.tmp_test_appdata; test-only APPDATA override'),
    source('scripts/server-path-audit/test-cleanup-archive.ps1',"cleanup-synthetic-",'synthetic_test_output','repo/.tmp/cleanup-synthetic-<GUID>; never real server data'),
    source('scripts/collect_react_profiler.cjs',"'benchmark-reports'",'performance_evidence','repo/.gstack/benchmark-reports; --out override supported'),
    source('scripts/deploy.ps1','"dist") $ZipName','build_output','repo/dist/SmartFactory_v<version>_Portable.zip and staging'),
    source('package.json','"from": "backend/dist/SmartFactoryBackend"','required_build_input','backend/dist and frontend/dist are package inputs; preserve'),
    source('scripts/collect-spot-connecttimeout-evidence.ps1',"SmartFactoryLogger_Evidence",'server_evidence','Desktop/SmartFactoryLogger_Evidence; EvidenceBase override supported'),
    source('scripts/invoke-spot-realtime-image-canary-120m.ps1','Join-Path $env:LOCALAPPDATA "SFLCanary"','server_evidence','LOCALAPPDATA/SFLCanary; explicit runtime evidence base supported'),
    source('scripts/qa_spot_image_server.ps1','Join-Path $env:TEMP','qa_output','TEMP/sfl-spot-image-server-qa-<stamp>.json; OutputPath override supported'),
    source('scripts/qa_spot_temperature_v25.ps1','Join-Path $env:TEMP','qa_output','TEMP/sfl-spot-temperature-v25-qa-<stamp>.json; OutputPath override supported'),
    source('scripts/collect_nsis_startup_trace.ps1','"smart-factory-startup-traces"','qa_output','TEMP/smart-factory-startup-traces'),
    source('scripts/server-stage-v1026/server-stage.ps1','Use the approved desktop transfer directory','legacy_transfer','Desktop/SmartFactory; delivered scripts retain hash-bound paths'),
    source('scripts/server-stage-v1026/repair-root-inbox-acl.ps1',"$root='C:\\ProgramData\\SFLOps'",'server_admin_data','ProgramData/SFLOps: inbox/releases/runs/audits/backups/tmp/inventory; metadata only locally'),
    source('backend/config.py','os.getenv("SFL_CONFIG_PATH")','protected_runtime','SFL_CONFIG_PATH or SMARTFACTORY_CONFIG override; never cleanup'),
    source('backend/config.py','return Path(base) / "SmartFactoryLogger"','protected_runtime','APPDATA/SmartFactoryLogger; config, logs, CSV, images, snapshots; configurable subpaths'),
    source('main.js',"app.getPath('userData')",'protected_runtime','Electron userData/debug_electron.log; temp fallback; never cleanup'),
    source('backend/app.py','Path(tempfile.gettempdir()) / "SmartFactoryLogger"','protected_runtime','TEMP/SmartFactoryLogger/logs/system fallback; never cleanup'),
    source('.gitignore','release_artifacts/','legacy_output_convention','repo/release_artifacts, qa_evidence, sf-health-*, .tmp_*, _tmp_*, _server_stdout*, tmp'),
  ];
}
function roots() {
  const found = [];
  const add = (p, origin) => {
    p = path.resolve(p);
    if (!found.some(r => same(r.path,p))) found.push({path:p,origin});
  };
  const exact = ['artifacts','release_artifacts','qa_evidence','.tmp','tmp','dist','backend/build','backend/dist','frontend/dist','.gstack/benchmark-reports','.gstack/build-verify','.gstack/deploy-reports','.gstack/qa-reports','.gstack/tmp'];
  for (const p of exact) add(path.join(repo,p),'source_catalog_or_repository_output');
  for (const e of fs.readdirSync(repo,{withFileTypes:true})) {
    if (/^(\.tmp[_-]|_tmp_|_server_stdout|sf-health-)/i.test(e.name) || ['server_stdout.zip','tmp_.bin'].includes(e.name)) add(path.join(repo,e.name),'gitignore_output_pattern');
  }
  const home = os.homedir();
  for (const [base,pattern] of [
    [path.join(home,'Desktop'),/^(test$|SmartFactory($|_)|SmartFactoryLogger_(Builds|Release|Transfer|Evidence)|v102[0-9].*\.(zip|ps1|txt)$|read-installed-v1026|repair-sflops)/i],
    [path.join(home,'Downloads'),/^(SmartFactory|smart-factory|SFL|v102[0-9])[^<>]*\.(zip|exe|ps1|txt)$/i],
    [os.tmpdir(),/^(sfl-|spot-|smart-factory-startup|SmartFactoryLogger|runtime_validation_)/i]
  ]) {
    if (!fs.existsSync(base)) continue;
    plain(base);
    for(const e of fs.readdirSync(base)) if(pattern.test(e)) add(path.join(base,e),'matching_project_transfer_or_diagnostic_name');
  }
  // These are evidence locations from the source, not operating installation/profile trees.
  for(const p of ['C:\\SFLCanary','C:\\tmp','C:\\temp']) {
    if (!fs.existsSync(p)) continue;
    if (/SFLCanary$/.test(p)) add(p,'source_declared_legacy_canary');
    else for(const name of fs.readdirSync(plain(p))) if(/^(sfl-|spot-|capture-spot|qa_spot|plc-transient-check|pr65-server-readonly)/i.test(name)) add(path.join(p,name),'source_declared_legacy_temp_prefix');
  }
  add(path.join(home,'AppData/Local/SFLCanary'),'source_declared_canary_evidence');
  return found.filter(r=>!found.some(parent=>parent!==r && inside(r.path,parent.path)));
}
function trackedFiles() {
  return new Set(execFileSync('git',['ls-files','-z'],{cwd:repo,encoding:'utf8',maxBuffer:20e6}).split('\0').filter(Boolean).map(p=>path.resolve(repo,p).toLowerCase()));
}
function buildCheckoutClass(relative, tracked, ignored) {
  const name=relative.replaceAll('\\','/');
  if(name.startsWith('.git/'))return 'PROTECT_GIT_METADATA';
  // Tracked files and configuration always win over generated-directory names.
  if(/(?:^|\/)(?:\.env(?:\.[^/]*)?|config[^/]*\.(?:ini|json|bak))$/i.test(name))return 'PROTECT_CONFIGURATION';
  if(tracked)return 'PROTECT_GIT_TRACKED_SOURCE';
  if(!ignored)return 'KEEP_UNTRACKED_REVIEW';
  if(/^(?:v2_next\/node_modules|v2_next\/frontend\/node_modules|v2_next\/backend\/(?:\.venv|browsers))\//.test(name))return 'CANDIDATE_REINSTALLABLE_DEPENDENCY';
  if(/^v2_next\/(?:\.mypy_cache|\.ruff_cache)\//.test(name)||/^v2_next\/.*\/__pycache__\/[^/]+\.pyc$/.test(name))return 'CANDIDATE_REGENERABLE_CACHE';
  if(name.startsWith('v2_next/backend/build/'))return 'CANDIDATE_REGENERABLE_BUILD_INTERMEDIATE';
  if(/^(?:v2_next\/dist|v2_next\/backend\/dist|v2_next\/frontend\/dist)\//.test(name))return 'KEEP_BUILD_OUTPUT_REVIEW';
  if(name.startsWith('v2_next/.tmp_test_appdata/'))return 'KEEP_TEST_EVIDENCE';
  return 'KEEP_IGNORED_REVIEW';
}
async function auditBuildCheckout() {
  // Fixed development checkout only. No checkout code, install, cleanup or network command runs.
  const root=path.join(os.homedir(),'Desktop','SmartFactoryLogger_Builds');
  const batch=path.join(root,'spot-tcp-connection-reuse-remediation_bfd9be7');
  const checkout=path.join(batch,'source');
  plain(indexPath);plain(checkout);plain(path.join(checkout,'.git'));
  if(!fs.lstatSync(path.join(checkout,'.git')).isDirectory())throw new Error('Standalone checkout required');
  if(JSON.stringify(fs.readdirSync(root))!==JSON.stringify([path.basename(batch)])||JSON.stringify(fs.readdirSync(batch))!==JSON.stringify(['source']))throw new Error('Build collection boundary changed');
  const registrySha=await hash(indexPath),index=readIndexForUpdate();
  if(index.host!==os.hostname()||!same(index.workspace,repo))throw new Error('Wrong host/workspace');
  if((index.migrations||[]).some(m=>m.state!=='COMPLETE')||index.plans.some(p=>p.state!=='COMPLETE'))throw new Error('Unfinished operation');
  const git=(cwd,args,input)=>execFileSync('git',['--no-optional-locks','-c','core.fsmonitor=false','-C',cwd,...args],{encoding:'utf8',input,timeout:60000,maxBuffer:30e6});
  const splitZ=text=>text.split('\0').filter(Boolean);
  const head=git(checkout,['rev-parse','HEAD']).trim();
  if(head!=='bfd9be785f7a87aa4150445945861a54bca98f33'||!same(path.resolve(git(checkout,['rev-parse','--show-toplevel']).trim()),checkout))throw new Error('Reviewed checkout identity changed');
  const status=git(checkout,['status','--porcelain=v1','-z','--untracked-files=all']);
  const tracked=new Set(splitZ(git(checkout,['ls-files','-z'])));
  const ignored=new Set(splitZ(git(checkout,['ls-files','--others','--ignored','--exclude-standard','-z'])));
  const refs=git(checkout,['for-each-ref','--format=%(objectname) %(refname)']);
  const objects=git(checkout,['rev-list','--objects','--all']).trim().split(/\r?\n/).map(line=>line.split(' ')[0]);
  if(!objects.every(id=>/^[0-9a-f]{40}$/.test(id)))throw new Error('Unexpected Git object identity');
  const checked=git(repo,['cat-file','--batch-check=%(objectname) %(objecttype)'],objects.join('\n')+'\n').trim().split(/\r?\n/);
  if(checked.length!==objects.length||checked.some((line,i)=>!line.startsWith(objects[i]+' ')))throw new Error('Incomplete Git object comparison');
  const gitIndexSha=await hash(path.join(checkout,'.git','index'));
  const inventory={files:[],dirs:[checkout],links:[],errors:[]};
  // The generic scanner intentionally excludes checkouts. This opt-in audit inspects this one only.
  for(const name of fs.readdirSync(checkout)){
    const child=walk(path.join(checkout,name));
    for(const field of ['files','dirs','links','errors'])inventory[field].push(...child[field]);
  }
  if(inventory.links.length||inventory.errors.length)throw new Error('Incomplete/linked checkout inventory; no audit published');
  const groups={},files=inventory.files.map(f=>{
    const relative=path.relative(checkout,f.path).split(path.sep).join('/');
    const classification=buildCheckoutClass(relative,tracked.has(relative),ignored.has(relative));
    const group=groups[classification]||={files:0,bytes:0};group.files++;group.bytes+=f.bytes;
    return {relative,bytes:f.bytes,mtime_ms:f.mtime_ms,classification};
  });
  const physical=new Set(files.map(f=>f.relative));
  if([...tracked,...ignored].some(name=>!physical.has(name)))throw new Error('Git file inventory differs from disk');
  const sourceSpecs=[
    ['.github/workflows/windows-release-artifact.yml','run: npm ci','Node dependency installation'],
    ['v2_next/scripts/deploy.ps1','python -m venv $BackendVenvDir','backend/.venv creation'],
    ['v2_next/scripts/deploy.ps1','-m pip install','Python dependency installation'],
    ['v2_next/scripts/deploy.ps1','backend\\browsers','Bundled browser installation path'],
    ['v2_next/scripts/deploy.ps1','-m playwright install chromium','Browser installation'],
    ['v2_next/scripts/deploy.ps1','-m PyInstaller','backend/build and backend/dist producer'],
    ['v2_next/scripts/deploy.ps1','$PortableDir =','dist portable staging'],
    ['v2_next/scripts/deploy.ps1','$ZipPath =','dist portable ZIP'],
    ['v2_next/package.json','"from": "backend/dist/SmartFactoryBackend"','Electron backend bundle input'],
    ['v2_next/package.json','"from": "frontend/dist"','Electron frontend bundle input'],
    ['v2_next/package.json','-m mypy','Type checker cache producer'],
    ['v2_next/package.json','-m ruff check','Lint cache producer'],
    ['v2_next/scripts/run_backend_unittest.cjs',"'.tmp_test_appdata'",'Test APPDATA redirection']
  ];
  const sources=[];
  for(const [relative,needle,purpose] of sourceSpecs){
    const file=plain(path.join(checkout,relative)),lines=fs.readFileSync(file,'utf8').split(/\r?\n/);
    const line=lines.findIndex(text=>text.includes(needle))+1;
    if(!line)throw new Error('Historical storage logic changed');
    sources.push({relative,line,purpose,sha256:await hash(file)});
  }
  // Unique output is not disposable just because it was generated. Bind top-level packages.
  const packages=[];
  for(const f of files.filter(f=>/^v2_next\/dist\/[^/]+\.(?:exe|zip|blockmap)$/.test(f.relative))){
    const sha256=await hash(path.join(checkout,f.relative)),witnesses=[];
    for(const m of index.migrations)for(const kept of m.files){
      if(kept.destination&&kept.bytes===f.bytes&&kept.sha256===sha256&&await hash(kept.destination)===sha256)witnesses.push(kept.destination);
    }
    packages.push({relative:f.relative,bytes:f.bytes,sha256,verified_migrated_copies:witnesses});
  }
  if(git(checkout,['rev-parse','HEAD']).trim()!==head||git(checkout,['status','--porcelain=v1','-z','--untracked-files=all'])!==status||git(checkout,['for-each-ref','--format=%(objectname) %(refname)'])!==refs||await hash(path.join(checkout,'.git','index'))!==gitIndexSha)throw new Error('Checkout changed during audit');
  for(const f of files){const s=fs.lstatSync(path.join(checkout,f.relative));if(!s.isFile()||s.size!==f.bytes||s.mtimeMs!==f.mtime_ms)throw new Error('Inventory changed during audit');}
  const audit={id:crypto.randomUUID(),kind:'DESKTOP_BUILDS_CHECKOUT_CLASSIFICATION',at:new Date().toISOString(),root,checkout,state:'CLASSIFIED_NOT_APPROVED_FOR_DELETION',head,git:{tracked_files:tracked.size,ignored_files:ignored.size,worktree_clean:status.length===0,reachable_objects:objects.length,missing_objects_in_current_repository:checked.filter(line=>line.endsWith(' missing')).length,index_sha256:gitIndexSha},groups,files,directories:inventory.dirs.map(p=>path.relative(checkout,p)),source_anchors:sources,packages,source_writes:0,deleted_files:0,moved_files:0,remote_server_operations:0,limitations:['Candidates are not deletion approvals; dependency reinstall/build reproducibility was not tested.','No full-content/ADS/ACL deletion manifest was created; sizes and mtimes are a live, non-atomic inventory.','Git object coverage excludes reflog-only/unreachable objects and does not authorize deleting .git or source.','Configuration contents are not read; no historical helper, package, installer or build script is executed.']};
  if(await hash(indexPath)!==registrySha)throw new Error('Concurrent registry change');
  index.audits=[...(index.audits||[]),audit];index.updated_at=audit.at;
  index.history.push({at:audit.at,kind:audit.kind,audit_id:audit.id,state:audit.state,deleted_files:0,moved_files:0,remote_server_operations:0});
  save(index);
  console.log(JSON.stringify({id:audit.id,state:audit.state,files:files.length,bytes:files.reduce((n,f)=>n+f.bytes,0),groups,git:audit.git,packages:packages.map(p=>({relative:p.relative,bytes:p.bytes,verified_copy_count:p.verified_migrated_copies.length}))}));
}
async function auditBuildDependencies() {
  plain(indexPath);
  const initial=await hash(indexPath),index=readIndexForUpdate();
  if(index.host!==os.hostname()||!same(index.workspace,repo))throw new Error('Wrong host/workspace');
  assertMigrationStates(index);
  if((index.migrations||[]).some(m=>m.state!=='COMPLETE')||(index.plans||[]).some(p=>p.state!=='COMPLETE'))throw new Error('Unfinished operation');
  const audit=await require('./review-build-dependencies.cjs').review(index,{plain,walk,hash});
  if(await hash(indexPath)!==initial)throw new Error('Concurrent registry change');
  index.audits=[...(index.audits||[]),audit];index.updated_at=audit.at;
  index.history.push({at:audit.at,kind:audit.kind,audit_id:audit.id,state:audit.state,deleted_files:0,moved_files:0,remote_server_operations:0});
  save(index);
  console.log(JSON.stringify({id:audit.id,state:audit.state,groups:audit.groups,node:audit.node.map(n=>({relative:n.relative,matching_versions:n.matching_versions,optional_absent:n.absent_optional_other_platform.length,problems:n.problems})),python:{distributions:audit.python.distributions.length,record_hash_matches:audit.python.distributions.reduce((n,d)=>n+d.hashed_matches,0),problems:audit.python.distributions.flatMap(d=>d.problems.map(p=>({name:d.name,...p}))),unrecorded_files:audit.python.unrecorded_files,exact_requirements:audit.python.requirements.filter(r=>r.exact).length},browsers:audit.browsers}));
}
async function scan() {
  const old = fs.existsSync(indexPath) ? readIndexForUpdate() : {};
  if((old.plans||[]).some(p=>p.state==='DELETING'))throw new Error('Deletion in progress; do not overwrite the registry');
  desktopEvidenceRoot(old);assertMigrationStates(old); // Do not overwrite a partial migration's journal.
  const index={schema:'sfl-verification-registry-v1',host:os.hostname(),workspace:repo,updated_at:new Date().toISOString(),source_catalog:sourceCatalog(),roots:[],files:[],links:[],directories:[],history:old.history||[],plans:old.plans||[],migrations:old.migrations||[],audits:old.audits||[],limitations:[
    'Development host only; remote server filesystem not accessed.',
    'No whole-disk claim: project source defaults, output conventions, and named transfer locations scanned; unknown custom --out/OutputRoot paths may exist.',
    'Operating profiles, installed programs, environment credentials, source checkouts and linked targets excluded.',
    'Logical file bytes are not allocated or recoverable disk bytes; hard links/compression may differ.',
    'Names alone never authorize deletion. Unclassified entries remain kept.'
  ]};
  const tracked=trackedFiles();
  const migratedFiles=new Map(index.migrations.filter(m=>m.state==='COMPLETE').flatMap(m=>m.files).filter(f=>f.destination).map(f=>[f.destination.toLowerCase(),f]));
  const recoveryFiles=new Set((index.audits||[]).filter(a=>a.kind==='DESKTOP_BUILDS_DEPENDENCY_CLEANUP_PLAN').flatMap(a=>a.keep_files.map(f=>path.join(a.keep_root,...f.relative.split('/')).toLowerCase())));
  const stageKeepers=new Set(stageExtractionRecords(index).flatMap(a=>a.files.map(f=>f.keeper.toLowerCase())));
  const attestationKeepers=new Set(attestationExtractionRecords(index).flatMap(a=>a.files.map(f=>f.keeper.toLowerCase())));
  const isolatedEvidence=new Set(isolatedTestCacheRecords(index).flatMap(a=>a.preserved_files.map(f=>f.path.toLowerCase())));
  const buildEvidence=new Set(buildIntermediateRecords(index).flatMap(a=>a.preserved_files.map(f=>f.path.toLowerCase())));
  const browserState=new Set(chromeTestCacheRecords(index).flatMap(a=>a.preserved_files.map(f=>f.path.toLowerCase())));
  for(const root of roots()) {
    if(!fs.existsSync(root.path)) {index.roots.push({...root,state:'ABSENT'});continue;}
    if(index.roots.length % 50 === 0) console.log('[SCAN] project paths inspected='+index.roots.length);
    try {
      plain(root.path);
      const items=walk(root.path);
      index.roots.push({...root,state:items.errors.length?'PARTIAL':'INVENTORIED',file_count:items.files.length,bytes:items.files.reduce((n,f)=>n+f.bytes,0),errors:items.errors});
      for(const f of items.files) {
        f.root=root.path;f.state='KEEP_NOT_PROVEN_DISPOSABLE';
        if(tracked.has(f.path.toLowerCase()))f.state='PROTECT_GIT_TRACKED';
        else if(['backend/dist','frontend/dist','.tmp/v1026x1'].some(p=>inside(f.path,path.resolve(repo,p))))f.state='PROTECT_CURRENT_BUILD_INPUT';
        else if(/(?:config[^\\/]*\.(?:ini|json)|\.bak)$/i.test(f.path))f.state='KEEP_CONFIGURATION_OR_BACKUP_COPY';
        else if(/\.(?:csv|json|jsonl|log|png|md|txt)$/i.test(f.path))f.state='KEEP_EVIDENCE_OR_SUPPORTING_SOURCE';
        else if(/\.(?:zip|exe|7z)$/i.test(f.path))f.state='KEEP_PACKAGE_NOT_PROVEN_REDUNDANT';
        const migrated=migratedFiles.get(f.path.toLowerCase());
        if(migrated){f.original_path=migrated.source;f.migration_sha256=migrated.sha256;f.state='KEEP_MIGRATED_SERVER_EVIDENCE';}
        if(recoveryFiles.has(f.path.toLowerCase()))f.state='PROTECT_DEPENDENCY_RECOVERY';
        if(stageKeepers.has(f.path.toLowerCase()))f.state='PROTECT_STAGE_EXTRACTION_KEEPER';
        if(attestationKeepers.has(f.path.toLowerCase()))f.state='PROTECT_ATTESTATION_EXTRACTION_KEEPER';
        if(isolatedEvidence.has(f.path.toLowerCase()))f.state='PROTECT_ISOLATED_TEST_EVIDENCE';
        if(buildEvidence.has(f.path.toLowerCase()))f.state='PROTECT_BUILD_DIAGNOSTIC_EVIDENCE';
        if(browserState.has(f.path.toLowerCase()))f.state='PROTECT_RETAINED_BROWSER_PROFILE';
        index.files.push(f);
      }
      index.directories.push(...items.dirs);index.links.push(...items.links);
    }catch(e){index.roots.push({...root,state:'EXCLUDED',error:e.message});}
  }
  index.protected_roots=[
    'C:\\ProgramData\\SFLOps',path.join(os.homedir(),'AppData/Roaming/SmartFactoryLogger'),path.join(os.homedir(),'AppData/Roaming/smart-factory-logger-v2'),path.join(os.homedir(),'AppData/Local/Programs/smart-factory-logger-v2'),path.join(os.tmpdir(),'SmartFactoryLogger')
  ].map(p=>({path:p,exists:fs.existsSync(p),state:'PROTECT_NO_RECURSIVE_SCAN_OR_MUTATION'}));
  // Explicit approved mappings only; never recursively inventory SFLOps or claim a fresh hash check here.
  for(const {base,files} of distArchiveRecords(index)){
    index.roots.push({path:base,origin:'APPROVED_EXACT_ARCHIVE_MAPPING',state:'PROTECTED_MAPPING_NOT_RESCANNED',file_count:files.length,bytes:files.reduce((n,f)=>n+f.bytes,0),errors:[]});
    index.files.push(...files.map(f=>({path:f.destination,root:base,bytes:f.bytes,state:'PROTECT_MIGRATED_CI_RELEASE',original_path:f.path,migration_sha256:f.sha256})));
  }
  for(const item of index.source_catalog)item.source_sha256=await hash(path.join(repo,item.source));
  index.environment_path_overrides=['SFL_CONFIG_PATH','SMARTFACTORY_CONFIG'].map(name=>({name,state:process.env[name]?'SET_PROTECTED_CUSTOM_PATH':'NOT_SET_IN_INVENTORY_PROCESS',path:process.env[name]||null}));
  index.summary={files:index.files.length,bytes:index.files.reduce((n,f)=>n+f.bytes,0),roots:index.roots.length,links:index.links.length,partial_roots:index.roots.filter(r=>['PARTIAL','EXCLUDED'].includes(r.state)).length,deleted_files:index.history.reduce((n,e)=>n+(e.deleted_files||0),0),deleted_bytes:index.history.reduce((n,e)=>n+(e.deleted_bytes||0),0),migrated_files:index.migrations.filter(m=>m.state==='COMPLETE').reduce((n,m)=>n+m.files.filter(f=>f.destination).length,0)};
  index.summary.migrated_files+=distArchiveRecords(index).reduce((n,r)=>n+r.files.length,0);
  save(index);console.log(JSON.stringify(index.summary));
}
async function prepareDesktopMigration() {
  plain(indexPath);plain(desktopSource);plain(path.join(repo,'artifacts'));
  const index=readIndexForUpdate();
  if(index.host!==os.hostname()||!same(index.workspace,repo))throw new Error('Wrong host/workspace');
  if((index.migrations||[]).some(m=>m.kind==='DESKTOP_TEST_MIGRATION')||index.plans.some(p=>p.state!=='COMPLETE'))throw new Error('Prior migration or incomplete deletion plan');
  if(fs.existsSync(desktopDestination))throw new Error('Destination already exists; never overwrite evidence');
  const items=walk(desktopSource);
  if(items.links.length||items.errors.length||items.dirs.length!==1||!items.files.length)throw new Error('Expected the reviewed flat, plain source folder');
  const migration={id:crypto.randomUUID(),kind:'DESKTOP_TEST_MIGRATION',state:'PLANNED',created_at:new Date().toISOString(),source:desktopSource,destination:desktopDestination,source_sddl:null,destination_sddl:null,copy_verified_count:0,source_removed_count:0,error:null,files:[]};
  for(const f of items.files){
    const name=path.basename(f.path);
    migration.files.push({name,source:f.path,destination:path.join(desktopDestination,name),bytes:f.bytes,mtime_ms:f.mtime_ms,sha256:await hash(f.path),state:'PLANNED'});
  }
  const receipt=migration.files.find(f=>f.name==='result.json');
  if(receipt?.sha256!=='D23EFD1787BB00A61A36C115929B3AFE9401DFF085F993CDE0FFD58E445A49B5')throw new Error('Expected installed receipt not found');
  index.migrations=[...(index.migrations||[]),migration];save(index);
  console.log(JSON.stringify({id:migration.id,source:migration.source,destination:migration.destination,files:migration.files.length,bytes:migration.files.reduce((n,f)=>n+f.bytes,0),index_sha256:await hash(indexPath)}));
}
async function prepareTransferMigration() {
  plain(indexPath);plain(transferSource);plain(path.join(repo,'artifacts','server-evidence'));
  const index=readIndexForUpdate();
  if(index.host!==os.hostname()||!same(index.workspace,repo))throw new Error('Wrong host/workspace');
  if((index.migrations||[]).some(m=>m.state!=='COMPLETE'||m.kind==='DESKTOP_SMARTFACTORY_MIGRATION')||index.plans.some(p=>p.state!=='COMPLETE'))throw new Error('Prior transfer migration or unfinished operation');
  if(fs.existsSync(transferDestination))throw new Error('Destination already exists');
  const items=walk(transferSource);
  if(items.links.length||items.errors.length||items.files.length!==65||items.dirs.length!==14)throw new Error('Reviewed inventory changed');
  const migration={id:crypto.randomUUID(),kind:'DESKTOP_SMARTFACTORY_MIGRATION',state:'PLANNED',created_at:new Date().toISOString(),source:transferSource,destination:transferDestination,source_sddl:null,destination_sddl:null,copy_verified_count:0,source_removed_count:0,error:null,files:[],directories:[]};
  for(const f of items.files){
    const relative=path.relative(transferSource,f.path),rule=archiveDuplicateRule(relative.replaceAll('\\','/'));
    migration.files.push({name:relative,source:f.path,destination:rule?null:path.join(transferDestination,relative),bytes:f.bytes,mtime_ms:f.mtime_ms,sha256:await hash(f.path),state:'PLANNED',action:rule?'ARCHIVE_DUPLICATE':'COPY',original_sddl:null,creation_time_utc:null,last_write_time_utc:null,attributes:null,retained_archive:rule?{path:path.join(transferDestination,rule.zip),source:path.join(transferSource,rule.zip),entry:rule.entry,sha256:null}:null});
  }
  for(const f of migration.files.filter(f=>f.retained_archive)){
    const keeper=migration.files.find(k=>same(k.source,f.retained_archive.source)&&k.action==='COPY');
    if(!keeper||!same(keeper.destination,f.retained_archive.path))throw new Error('Archive is not in retained copy set');
    f.retained_archive.sha256=keeper.sha256;
  }
  const duplicates=migration.files.filter(f=>f.retained_archive);
  if(duplicates.length!==13)throw new Error('Reviewed archive duplicate set changed');
  for(const dir of items.dirs.sort((a,b)=>a.length-b.length)){
    const relative=path.relative(transferSource,dir);
    const keep=!relative||migration.files.some(f=>f.destination&&inside(f.source,dir));
    migration.directories.push({source:dir,destination:keep?path.join(transferDestination,relative):null,original_sddl:null});
  }
  migration.reference_review={at:new Date().toISOString(),local_source_references:'Only archived historical helpers and server-only launch/audit paths; no active local consumer found in scripts/docs search.',policy:'Do not rewrite historic helpers or server paths; archive for reference, not execution.',external_duplicate_files:16,external_duplicate_policy:'Build/temp witnesses are mutable and are not used as canonical retained copies.'};
  index.migrations.push(migration);index.updated_at=new Date().toISOString();save(index);
  console.log(JSON.stringify({id:migration.id,files:migration.files.length,copied:migration.files.length-duplicates.length,archived_duplicates:duplicates.length,duplicate_bytes:duplicates.reduce((n,f)=>n+f.bytes,0),source_bytes:items.files.reduce((n,f)=>n+f.bytes,0),destination:transferDestination,index_sha256:await hash(indexPath)}));
}
async function prepareReleaseMigration() {
  plain(indexPath);plain(releaseSource);plain(path.join(repo,'artifacts','server-evidence'));
  const index=readIndexForUpdate();
  if(index.host!==os.hostname()||!same(index.workspace,repo))throw new Error('Wrong host/workspace');
  if((index.migrations||[]).some(m=>m.state!=='COMPLETE'||m.kind==='DESKTOP_RELEASE_MIGRATION')||index.plans.some(p=>p.state!=='COMPLETE'))throw new Error('Prior release migration or unfinished operation');
  if(fs.existsSync(releaseDestination))throw new Error('Destination already exists');
  const items=walk(releaseSource);
  if(items.links.length||items.errors.length||items.files.length!==11403||items.dirs.length!==756)throw new Error('Reviewed release inventory changed');
  const migration={id:crypto.randomUUID(),kind:'DESKTOP_RELEASE_MIGRATION',state:'PLANNED',created_at:new Date().toISOString(),source:releaseSource,destination:releaseDestination,source_sddl:null,destination_sddl:null,copy_verified_count:0,source_removed_count:0,error:null,files:[],directories:[]};
  for(const f of items.files){
    const name=path.relative(releaseSource,f.path);
    migration.files.push({name,source:f.path,destination:path.join(releaseDestination,releaseDestinationName(name)),bytes:f.bytes,mtime_ms:f.mtime_ms,sha256:await hash(f.path),state:'PLANNED',action:'COPY',original_sddl:null,creation_time_utc:null,last_write_time_utc:null,attributes:null,retained_archive:null,retained_file:null});
    if(migration.files.length%2000===0)console.log('[PLAN HASH] '+migration.files.length+'/'+items.files.length);
  }
  const keepers=releaseRetention(migration.files);
  for(const f of migration.files){
    const keeper=keepers.get(f.source);
    if(keeper===f)continue;
    f.action='FILE_DUPLICATE';f.destination=null;
    f.retained_file={source:keeper.source,path:keeper.destination,bytes:keeper.bytes,sha256:keeper.sha256};
    if(!f.retained_file.path)throw new Error('Retention may not form a chain');
  }
  const copies=migration.files.filter(f=>f.destination),duplicates=migration.files.filter(f=>f.retained_file);
  const maxPath=Math.max(...copies.map(f=>f.destination.length));
  if(maxPath>259)throw new Error('Retained path exceeds tested local path budget');
  for(const dir of items.dirs.sort((a,b)=>a.length-b.length)){
    const relative=path.relative(releaseSource,dir),keep=!relative||copies.some(f=>inside(f.source,dir));
    migration.directories.push({source:dir,destination:keep?path.join(releaseDestination,releaseDestinationName(relative)):null,original_sddl:null});
  }
  const producer=migration.files.find(f=>f.name===path.join('staging_575e869','assemble_release_575e869.ps1'));
  if(!producer)throw new Error('Reviewed release producer missing');
  migration.reference_review={at:new Date().toISOString(),source_anchor:{original_path:producer.source,sha256:producer.sha256,parameter_line:19,create_release_line:371,write_identity_line:522},local_source_references:'No active repository script reference found; historical assembly/operator helpers are preserved without edits.',policy:'Archive only; do not execute historical helpers or partial staging trees. Full published release and field-kit file sets remain copied.',dedup_rule:'Same leaf name, length and SHA256 within this collection only; every removed file points directly to a copied keeper.',max_retained_path_chars:maxPath};
  index.migrations.push(migration);index.updated_at=new Date().toISOString();save(index);
  console.log(JSON.stringify({id:migration.id,files:migration.files.length,copied:copies.length,file_duplicates:duplicates.length,duplicate_bytes:duplicates.reduce((n,f)=>n+f.bytes,0),copied_bytes:copies.reduce((n,f)=>n+f.bytes,0),max_retained_path_chars:maxPath,destination:releaseDestination,index_sha256:await hash(indexPath)}));
}
async function prepareTransferBatchMigrations() {
  plain(indexPath);plain(path.join(repo,'artifacts','server-evidence'));
  const index=readIndexForUpdate(),specs=transferBatchSpecs();
  if(index.host!==os.hostname()||!same(index.workspace,repo))throw new Error('Wrong host/workspace');
  if((index.migrations||[]).some(m=>m.state!=='COMPLETE'||specs.some(s=>s.kind===m.kind))||index.plans.some(p=>p.state!=='COMPLETE'))throw new Error('Prior batch migration or unfinished operation');
  const migrations=[];
  for(const spec of specs){
    const source=path.join(os.homedir(),'Desktop',spec.source_leaf),destination=path.join(repo,'artifacts','server-evidence',spec.collection);
    plain(source);
    if(fs.existsSync(destination))throw new Error('Transfer destination exists');
    const items=walk(source);
    if(items.links.length||items.errors.length||items.dirs.length!==1||items.files.length!==spec.count)throw new Error('Reviewed flat transfer inventory changed');
    const migration={id:crypto.randomUUID(),kind:spec.kind,collection:spec.collection,state:'PLANNED',created_at:new Date().toISOString(),source,destination,source_sddl:null,destination_sddl:null,copy_verified_count:0,source_removed_count:0,error:null,files:[],directories:[{source,destination,original_sddl:null}]};
    for(const f of items.files){
      const name=path.basename(f.path);
      migration.files.push({name,source:f.path,destination:path.join(destination,name),bytes:f.bytes,mtime_ms:f.mtime_ms,sha256:await hash(f.path),state:'PLANNED',action:'COPY',original_sddl:null,creation_time_utc:null,last_write_time_utc:null,attributes:null,retained_archive:null,retained_file:null});
    }
    const zips=migration.files.filter(f=>f.name.endsWith('.zip'));
    if(zips.length!==1||zips[0].sha256!==spec.zip_sha256)throw new Error('Reviewed transfer ZIP identity changed');
    for(const f of migration.files.filter(f=>f.name.endsWith('.zip')||f.name.endsWith('.ps1'))){
      const sidecar=migration.files.find(s=>s.name===f.name+'.sha256.txt');
      if(!sidecar||fs.readFileSync(plain(sidecar.source),'utf8').trim()!==f.sha256)throw new Error('Transfer sidecar does not bind its payload');
    }
    if(spec.revision<3&&!migration.files.some(f=>f.name==='SUPERSEDED_BY_R'+(spec.revision+1)+'_DO_NOT_USE.txt'))throw new Error('Superseded marker missing');
    migration.reference_review={at:new Date().toISOString(),creation_source_status:'NOT_FOUND_IN_CURRENT_REPOSITORY',local_source_references:'No active writer/consumer references found in scripts, docs, README, AGENTS, package.json or main.js.',policy:'Historical transfer archive only. Retain superseded warnings and all distinct ZIP revisions; do not execute installers or helpers.',revision_status:spec.revision<3?'SUPERSEDED_DO_NOT_USE':'HISTORICAL_NOT_CURRENT_DEPLOYMENT_APPROVAL',artifact_duplicate_matches:0};
    migrations.push(migration);
  }
  index.migrations.push(...migrations);index.updated_at=new Date().toISOString();save(index);
  console.log(JSON.stringify({plans:migrations.map(m=>({id:m.id,collection:m.collection,files:m.files.length,bytes:m.files.reduce((n,f)=>n+f.bytes,0),destination:m.destination})),index_sha256:await hash(indexPath)}));
}
const regeneratedTargets = [
  'artifacts/v1026-electron44-local-validation-20260911/electron41-dist',
  'artifacts/v1026-electron44-local-validation-20260911/package-check',
  '.tmp_electron_cache'
].map(p=>path.resolve(repo,p));
async function planExact(targets) {
  const index=readIndexForUpdate();
  if(index.host!==os.hostname() || !same(index.workspace,repo))throw new Error('Wrong host/workspace');
  const plan={id:crypto.randomUUID(),created_at:new Date().toISOString(),state:'PLANNED_NOT_DELETED',files:[],directories:[],reason:'REVIEWED_REGENERABLE_LOCAL_TEST_BINARIES',authority:'2026-09-16 user: delete unnecessary verification files; preserve unique evidence and runtime'};
  for(const relative of targets) {
    const p=path.resolve(repo,relative);plain(p);
    // Deliberately narrow executable deletion scope. Inventory can cover much more.
    if(!regeneratedTargets.some(t=>same(t,p)))throw new Error('Not an approved reproducible subtree: '+p);
    const items=walk(p);
    if(items.links.length||items.errors.length)throw new Error('Incomplete or linked target');
    const tracked=trackedFiles();
    for(const f of items.files) {
      if(tracked.has(f.path.toLowerCase()))throw new Error('Tracked file');
      plan.files.push({...f,sha256:await hash(f.path),state:'PLANNED'});
    }
    plan.directories.push(...items.dirs);
  }
  if(!plan.files.length)throw new Error('Empty plan');
  index.plans.push(plan);index.updated_at=new Date().toISOString();save(index);
  console.log(JSON.stringify({id:plan.id,files:plan.files.length,bytes:plan.files.reduce((n,f)=>n+f.bytes,0),index_sha256:await hash(indexPath)}));
}
async function planDuplicateDirs() {
  const index=readIndexForUpdate();
  const plan={id:crypto.randomUUID(),created_at:new Date().toISOString(),state:'PLANNED_NOT_DELETED',files:[],directories:[],reason:'EXACT_DUPLICATE_TEST_EXTRACTIONS',authority:'2026-09-16 user: delete unnecessary verification files; preserve retained byte-identical source'};
  const pairs=[
    ['.tmp/v1023-stage-helper-test-20260903/destination2','.tmp/v1023-stage-helper-test-20260903/destination'],
    ['.tmp/v1023-stage-helper-test-20260903/destination3','.tmp/v1023-stage-helper-test-20260903/destination'],
    ['artifacts/_validate_field_kit_20260717_200829','artifacts/runtime-error-root-cause-validation-field-kit-20260717_200829'],
    ['artifacts/_validate_field_kit_20260717_203214','artifacts/runtime-error-root-cause-validation-field-kit-20260717_203214'],
    ['artifacts/_validate_runtime-error-root-cause-validation-field-kit-20260721_120623','artifacts/runtime-error-root-cause-validation-field-kit-20260721_120623'],
    ['artifacts/_validate_runtime-error-root-cause-validation-field-kit-20260721_133001','artifacts/runtime-error-root-cause-validation-field-kit-20260721_133001']
  ];
  for(const [target,keeper] of pairs){
    const a=path.resolve(repo,target),b=path.resolve(repo,keeper);plain(a);plain(b);
    const av=walk(a),bv=walk(b);
    if(av.links.length||bv.links.length||av.errors.length||bv.errors.length)throw new Error('Unsafe duplicate boundary');
    const map=new Map(bv.files.map(f=>[path.relative(b,f.path),f]));
    const dirA=av.dirs.map(p=>path.relative(a,p)).sort(),dirB=bv.dirs.map(p=>path.relative(b,p)).sort();
    if(av.files.length!==bv.files.length||JSON.stringify(dirA)!==JSON.stringify(dirB)) {console.log('[KEEP NOT EXACT] '+target);continue;}
    const rows=[];
    for(const f of av.files){
      const witness=map.get(path.relative(a,f.path));
      if(!witness||witness.bytes!==f.bytes){rows.length=0;break;}
      const sha=await hash(f.path);
      if(sha!==await hash(witness.path)){rows.length=0;break;}
      rows.push({...f,sha256:sha,state:'PLANNED',retained_copy:witness.path});
    }
    if(rows.length!==av.files.length||!rows.length){console.log('[KEEP NOT EXACT] '+target);continue;}
    plan.files.push(...rows);plan.directories.push(...av.dirs);
  }
  if(!plan.files.length)throw new Error('No exact duplicates');
  index.plans.push(plan);save(index);
  console.log(JSON.stringify({id:plan.id,files:plan.files.length,bytes:plan.files.reduce((n,f)=>n+f.bytes,0),index_sha256:await hash(indexPath)}));
}
function recoverJournal() {
  // Repair only the failed pre-delete registry publication, retaining its history.
  const staging=indexPath+'.writing';plain(indexPath);plain(staging);
  const old=readIndexForUpdate(),next=JSON.parse(fs.readFileSync(staging,'utf8'));
  if(old.host!==os.hostname()||next.host!==old.host||!same(next.workspace,repo)||next.history.length!==old.history.length+1)throw new Error('Unexpected pending journal');
  const event=next.history.at(-1);
  if(event.state!=='IN_PROGRESS'||event.deleted_files!==0)throw new Error('Not a pre-delete journal failure');
  for(const id of event.plan_ids){
    const a=old.plans.find(p=>p.id===id),b=next.plans.find(p=>p.id===id);
    if(a?.state!=='PLANNED_NOT_DELETED'||b?.state!=='DELETING'||JSON.stringify(a.files)!==JSON.stringify(b.files))throw new Error('Plans changed');
    for(const f of a.files)if(!fs.existsSync(f.path))throw new Error('Candidate missing; manual reconciliation required');
    b.state='PLANNED_NOT_DELETED';
  }
  event.state='PREDELETE_JOURNAL_FAILED_NO_DELETION';
  event.error='PowerShell File.Replace null-string binding failed before the first deletion; corrected to .NET overwrite rename.';
  const fd=fs.openSync(staging,'w');
  try{fs.writeFileSync(fd,JSON.stringify(next));fs.fsyncSync(fd);}finally{fs.closeSync(fd);}
  fs.renameSync(staging,indexPath);
  console.log('Pre-delete journal reconciled; no target file was deleted.');
}
async function verify() {
  const index=readIndexForUpdate();
  assertReviewedCleanupStates(index);
  for(const a of chromeTestCacheRecords(index)){
    for(const f of a.files)if(fs.existsSync(f.path))throw new Error('Removed Chrome cache reappeared; review browser reuse');
    for(const f of a.preserved_files)if(await hash(f.path)!==f.sha256)throw new Error('Preserved Chrome profile changed; review browser reuse');
    if(await hash(a.journal_path)!==a.journal_sha256)throw new Error('Chrome cleanup journal changed');
  }
  for(const a of buildIntermediateRecords(index)){
    for(const f of a.files)if(fs.existsSync(f.path))throw new Error('Removed build intermediate reappeared');
    for(const f of a.preserved_files)if(await hash(f.path)!==f.sha256)throw new Error('Build diagnostic evidence changed');
    if(await hash(a.journal_path)!==a.journal_sha256)throw new Error('Build cleanup journal changed');
  }
  let isolatedCacheDeleted=0,isolatedEvidenceVerified=0;
  for(const a of isolatedTestCacheRecords(index)){
    for(const f of a.files){if(fs.existsSync(f.path))throw new Error('Removed isolated cache reappeared');isolatedCacheDeleted++;}
    for(const f of a.preserved_files){if(await hash(f.path)!==f.sha256)throw new Error('Isolated test evidence changed');isolatedEvidenceVerified++;}
    if(await hash(a.journal_path)!==a.journal_sha256)throw new Error('Isolated cache journal changed');
  }
  let attestationDeleted=0;const attestationKept=new Set();
  for(const a of attestationExtractionRecords(index)){
    for(const f of a.files){
      if(fs.existsSync(f.path))throw new Error('Attestation duplicate reappeared');attestationDeleted++;
      if(!attestationKept.has(f.keeper)){
        if(await hash(f.keeper)!==f.sha256)throw new Error('Attestation keeper changed');
        attestationKept.add(f.keeper);
      }
    }
    for(const f of a.preserved_files)if(await hash(f.path)!==f.sha256)throw new Error('Preserved attestation evidence changed');
    if(await hash(a.journal_path)!==a.journal_sha256)throw new Error('Attestation journal changed');
  }
  let stageDeleted=0,stageKept=0;
  for(const a of stageExtractionRecords(index)){
    for(const f of a.files){
      if(fs.existsSync(f.path))throw new Error('Stage extraction duplicate reappeared');stageDeleted++;
      if(await hash(f.keeper)!==f.sha256)throw new Error('Stage extraction keeper changed');stageKept++;
    }
    for(const f of a.preserved_files)if(await hash(f.path)!==f.sha256)throw new Error('Preserved stage test/delivery evidence changed');
    if(await hash(a.journal_path)!==a.journal_sha256)throw new Error('Stage extraction journal changed');
  }
  let distSourcesAbsent=0,distArchivesVerified=0;
  for(const {audit,files} of distArchiveRecords(index)){
    // Fail explicitly if this caller cannot read the private archive. Do not downgrade to a false PASS.
    const privatePaths=[...audit.plan.new_directories,...files.map(f=>f.destination),audit.completion.receipt_path];
    const aclCheck=String.raw`$ErrorActionPreference='Stop';$admin=[Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator);if(-not$admin){throw 'Administrator required to verify protected dist archive'};foreach($p in ([Console]::In.ReadToEnd()|ConvertFrom-Json)){$a=Get-Acl -LiteralPath $p;if(-not$a.AreAccessRulesProtected-or$a.GetOwner([Security.Principal.SecurityIdentifier]).Value-ne'S-1-5-32-544'){throw 'Archive ACL boundary differs'};$r=@($a.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]));if($r.Count-ne 2-or@($r|Where-Object {$_.IsInherited-or$_.IdentityReference.Value-notin@('S-1-5-18','S-1-5-32-544')-or$_.AccessControlType-ne'Allow'-or$_.FileSystemRights-ne'FullControl'}).Count){throw 'Archive rules differ'}}`;
    execFileSync('pwsh.exe',['-NoProfile','-NonInteractive','-Command',aclCheck],{input:JSON.stringify(privatePaths),encoding:'utf8',windowsHide:true,timeout:60000});
    for(const f of files){if(await hash(f.destination)!==f.sha256)throw new Error('Dist archive hash differs');distArchivesVerified++;}
    for(const f of audit.plan.files){if(fs.existsSync(f.path))throw new Error('Removed dist source reappeared');distSourcesAbsent++;}
    if(await hash(audit.completion.receipt_path)!==audit.completion.receipt_sha256)throw new Error('Protected dist receipt differs');
  }
  let absent=0,keepers=0;
  for(const plan of index.plans){
    if(plan.state!=='COMPLETE')throw new Error('Incomplete plan: '+plan.id);
    for(const f of plan.files){
      if(fs.existsSync(f.path))throw new Error('Deleted target still exists: '+f.path);
      absent++;
      if(f.retained_copy){
        if(await hash(f.retained_copy)!==f.sha256)throw new Error('Retained duplicate changed');
        keepers++;
      }
    }
  }
  const receipt=path.join(desktopEvidenceRoot(index),'result.json');
  if(await hash(receipt)!=='D23EFD1787BB00A61A36C115929B3AFE9401DFF085F993CDE0FFD58E445A49B5')throw new Error('Latest installed-tree receipt changed');
  for(const p of ['artifacts/v1026-electron44-local-validation-20260911/REPORT.md','artifacts/v1026-electron44-local-validation-20260911/completion.json','artifacts/v1026-release-prep-d7a1b20-20260911/installer-candidate-review-only'])if(!fs.existsSync(path.join(repo,p)))throw new Error('Required retained evidence missing');
  let migrated=0,archivedDuplicates=0,fileDuplicates=0;
  for(const migration of index.migrations||[]){
    if(migration.state!=='COMPLETE')throw new Error('Migration is not complete');
    if(fs.existsSync(migration.source))throw new Error('Retired source directory still exists');
    const retainedHashes=new Map();
    const retainedRecords=new Map(migration.files.filter(f=>f.destination).map(f=>[f.destination.toLowerCase(),f]));
    for(const f of migration.files.filter(f=>f.destination)){
      const actual=await hash(f.destination);
      if(actual!==f.sha256)throw new Error('Migrated file changed');
      retainedHashes.set(f.destination.toLowerCase(),actual);migrated++;
    }
    for(const f of migration.files.filter(f=>!f.destination)){
      if(f.retained_archive){archivedDuplicates++;continue;}
      const keeper=f.retained_file&&retainedRecords.get(f.retained_file.path.toLowerCase());
      if(!keeper||keeper.source!==f.retained_file.source||keeper.bytes!==f.bytes||keeper.sha256!==f.sha256||retainedHashes.get(keeper.destination.toLowerCase())!==f.sha256)throw new Error('Duplicate keeper changed or missing');
      const relative=migration.kind==='DESKTOP_RELEASE_MIGRATION'?releaseDestinationName(f.name):f.name;
      if(fs.existsSync(f.source)||fs.existsSync(path.join(migration.destination,relative)))throw new Error('Removed duplicate reappeared');
      fileDuplicates++;
    }
    if(migration.files.some(f=>f.retained_archive)){
      execFileSync('pwsh.exe',['-NoLogo','-NoProfile','-File',path.join(__dirname,'migrate-desktop-test.ps1'),'-Collection','desktop-smartfactory','-ExpectedIndexSha256',await hash(indexPath),'-MigrationId',migration.id,'-VerifyArchivesOnly'],{cwd:repo,encoding:'utf8',timeout:60000,maxBuffer:1e6});
    }
  }
  let reviewedDeleted=0,buildDiagnostics=0,cacheSources=0;
  for(const review of (index.audits||[]).filter(a=>a.kind==='DESKTOP_BUILDS_CACHE_REVIEW'&&a.cleanup)){
    const cleanup=review.cleanup,removed=review.records.filter(r=>r.action==='DELETE_CANDIDATE'),kept=review.records.filter(r=>r.action==='KEEP');
    const deletedPaths=new Set(cleanup.deleted_paths);
    if(cleanup.review_id!==review.id||removed.length!==95||kept.length!==7||cleanup.deleted_files!==95||cleanup.deleted_bytes!==35362418||deletedPaths.size!==95||removed.reduce((n,r)=>n+r.file.bytes,0)!==cleanup.deleted_bytes)throw new Error('Cache cleanup receipt differs');
    for(const record of removed){
      if(!deletedPaths.has(record.file.path)||fs.existsSync(record.file.path))throw new Error('Reviewed deleted cache is present or unrecorded');
      reviewedDeleted++;
      if(record.retained_source){if(await hash(record.retained_source.path)!==record.retained_source.sha256)throw new Error('Retained Python source changed');cacheSources++;}
    }
    for(const record of kept){if(await hash(record.file.path)!==record.file.sha256)throw new Error('Preserved build diagnostics changed');buildDiagnostics++;}
    if(await hash(review.build_spec.path)!==review.build_spec.sha256)throw new Error('Preserved build specification changed');
  }
  let dependencyDeleted=0,dependencyKept=0,dependencyDirectories=0;
  for(const plan of (index.audits||[]).filter(a=>a.kind==='DESKTOP_BUILDS_DEPENDENCY_CLEANUP_PLAN'&&a.cleanup)){
    const cleanup=plan.cleanup;
    if(cleanup.state!=='COMPLETE'||cleanup.deleted_files!==152043||cleanup.deleted_bytes!==3267552016||cleanup.file_states!==cleanup.id+':'+('D'.repeat(plan.files.length))||cleanup.directory_states!==cleanup.id+':'+('D'.repeat(cleanup.directory_order.length))||cleanup.deleted_directories!==cleanup.directory_order.length)throw new Error('Dependency cleanup receipt or per-item journal differs');
    const roots=new Map(plan.roots.map(r=>[r.id,r.root]));
    for(const record of plan.files){if(fs.existsSync(path.join(roots.get(record.root_id),...record.relative.split('/'))))throw new Error('Removed dependency reappeared');dependencyDeleted++;}
    for(const dir of cleanup.directory_order){if(fs.existsSync(dir))throw new Error('Removed dependency directory reappeared');dependencyDirectories++;}
    for(const record of plan.keep_files){if(await hash(path.join(plan.keep_root,...record.relative.split('/')))!==record.sha256)throw new Error('Dependency recovery file changed');dependencyKept++;}
    for(const record of plan.source_anchors)if(await hash(record.path)!==record.sha256)throw new Error('Historical source/package witness changed');
  }
  index.validation={at:new Date().toISOString(),state:'LOCAL_CLEANUP_RECONCILED',deleted_files_absent:absent+archivedDuplicates+fileDuplicates+reviewedDeleted+dependencyDeleted,retained_copy_hashes_verified:keepers,installed_tree_receipt_hash_unchanged:true,migrated_file_hashes_verified:migrated,archive_duplicate_entries_verified:archivedDuplicates,file_duplicate_mappings_verified:fileDuplicates,reviewed_cache_files_absent:reviewedDeleted,build_diagnostics_hashes_verified:buildDiagnostics,cache_source_hashes_verified:cacheSources,dependency_files_absent:dependencyDeleted,dependency_directories_absent:dependencyDirectories,dependency_recovery_hashes_verified:dependencyKept,remote_server_operations:0};
  index.validation.dependency_preflight_holds=(index.audits||[]).filter(a=>a.kind==='DESKTOP_DEPENDENCY_ACL_PREFLIGHT_HOLD'&&a.state==='HOLD_ACL_TRUST_UNRESOLVED').length;
  index.validation.dist_source_files_absent=distSourcesAbsent;index.validation.dist_archive_hashes_verified=distArchivesVerified;
  index.validation.stage_extraction_sources_absent=stageDeleted;index.validation.stage_extraction_keepers_verified=stageKept;
  index.validation.attestation_extraction_sources_absent=attestationDeleted;index.validation.attestation_extraction_keepers_verified=attestationKept.size;
  index.validation.isolated_cache_files_absent=isolatedCacheDeleted;index.validation.isolated_evidence_hashes_verified=isolatedEvidenceVerified;
  save(index);console.log(JSON.stringify(index.validation));
}
async function recordDependencyAclHold(expectedHash) {
  plain(indexPath);const original=await hash(indexPath);
  if(original!==expectedHash)throw new Error('External registry hash differs');
  const index=readIndexForUpdate();assertMigrationStates(index);
  if(index.host!==os.hostname()||os.hostname()!=='DESKTOP-SS5CURC'||index.workspace!==repo)throw new Error('Development host mismatch');
  const plan=index.audits.find(a=>a.id==='31bd411f-0c64-469c-91ed-f5c3acae335f');
  if(!plan||plan.cleanup||index.audits.some(a=>a.kind==='DESKTOP_DEPENDENCY_ACL_PREFLIGHT_HOLD'))throw new Error('Plan already attempted or hold already recorded');
  const snapshot=JSON.parse(execFileSync('pwsh.exe',['-NoLogo','-NoProfile','-File',path.join(__dirname,'read-dependency-acl.ps1')],{encoding:'utf8',windowsHide:true,timeout:60000,maxBuffer:2e6}));
  if(snapshot.roots.length!==8)throw new Error('ACL snapshot scope differs');
  const rootMap=new Map(plan.roots.map(r=>[r.id,r.root]));
  for(const row of snapshot.roots)if(rootMap.get(row.id)!==row.path)throw new Error('ACL snapshot path differs');
  const blocked=snapshot.roots.filter(r=>r.outside_writers.length);
  if(blocked.length!==4||blocked.some(r=>!r.id.startsWith('test-')))throw new Error('Unexpected ACL result; review separately');
  let present=0;for(const file of plan.files){const full=path.join(rootMap.get(file.root_id),...file.relative.split('/'));if(!fs.existsSync(full))throw new Error('Candidate missing; cannot attest zero deletion');present++;}
  const id=crypto.randomUUID(),at=new Date().toISOString();
  const audit={id,kind:'DESKTOP_DEPENDENCY_ACL_PREFLIGHT_HOLD',at,plan_id:plan.id,state:'HOLD_ACL_TRUST_UNRESOLVED',authority:'User approved the exact eight-root deletion proposal; this preflight did not authorize or perform permission changes.',result:'WHATIF_STOPPED_BEFORE_ANY_DELETION',reason:'Current operator/admin/SYSTEM-only trust check encountered inherited write grants to CodexSandboxUsers and ten unresolved SIDs in the four rehearsal dependency roots.',snapshot,candidate_files_confirmed_present:present,full_preflight_passed:false,hash_preflight_completed_files:0,deleted_files:0,deleted_bytes:0,deleted_directories:0,acl_writes:0,remote_server_operations:0,limitations:['Root ACL snapshot only; not all descendant ACLs/hashes or named streams were validated before HOLD.','Unresolved SID does not by itself prove compromise; sandbox-group identity was verified but other SID provenance remains unconfirmed.','No original candidate/keeper permissions changed. No automatic retry.'],next_action:'Resolve the extra writer provenance or obtain approval for a separately reviewed, backed-up ACL adjustment limited to the four candidate roots; do not change the entire repository ACL.'};
  audit.tooling=await Promise.all(['remove-dependency-cleanup.ps1','remove-dependency-cleanup.test.ps1','read-dependency-acl.ps1'].map(async source=>({source,sha256:await hash(path.join(repo,'scripts',source))})));
  if(await hash(indexPath)!==original)throw new Error('Concurrent registry change');
  index.audits.push(audit);index.history.push({at,kind:audit.kind,audit_id:id,plan_id:plan.id,state:audit.state,deleted_files:0,deleted_bytes:0,acl_writes:0});index.updated_at=at;
  save(index);console.log(JSON.stringify({id,state:audit.state,candidate_files_confirmed_present:present,blocked_root_count:blocked.length,deleted_files:0,acl_writes:0,index_sha256:await hash(indexPath)}));
}
async function recordDependencyAclToolingHold(expectedHash) {
  plain(indexPath);const original=await hash(indexPath);
  if(original!==expectedHash)throw new Error('External registry hash differs');
  const index=readIndexForUpdate();assertMigrationStates(index);
  if(index.host!==os.hostname()||os.hostname()!=='DESKTOP-SS5CURC'||index.workspace!==repo)throw new Error('Development host mismatch');
  const plan=index.audits.find(a=>a.id==='31bd411f-0c64-469c-91ed-f5c3acae335f');
  const hold=index.audits.find(a=>a.id==='6f4737da-d677-4cb1-b919-d79f48bd991d');
  if(!plan||plan.cleanup||!hold||hold.state!=='HOLD_ACL_TRUST_UNRESOLVED'||index.audits.some(a=>a.kind==='DESKTOP_DEPENDENCY_ACL_TOOLING_HOLD'))throw new Error('Unexpected or already recorded state');
  const snapshot=JSON.parse(execFileSync('pwsh.exe',['-NoLogo','-NoProfile','-File',path.join(__dirname,'read-dependency-acl.ps1')],{encoding:'utf8',windowsHide:true,timeout:60000,maxBuffer:2e6}));
  if(snapshot.roots.length!==8||snapshot.roots.some(r=>!hold.snapshot.roots.some(old=>old.id===r.id&&old.path===r.path&&old.sddl===r.sddl)))throw new Error('Root ACL differs from original HOLD');
  const rootMap=new Map(plan.roots.map(r=>[r.id,r.root]));
  for(const file of plan.files){const full=path.join(rootMap.get(file.root_id),...file.relative.split('/'));if(!fs.lstatSync(full).isFile())throw new Error('Candidate missing or changed type');}
  const fixtureRoots=['sfl-acl-test-2290279b6cf643018eb90572ed1000f5','sfl-acl-test-a8f36415ecbf42f7b98a09752b0ecf7f'].map(n=>path.join(os.tmpdir(),n));
  const fixtures=[];
  for(const root of fixtureRoots){
    plain(root);const tree=walk(root);
    if(tree.errors.length||tree.links.length||tree.files.length!==1||tree.files[0].path!==path.join(root,'child','sample.txt')||tree.files[0].bytes!==7||fs.readFileSync(tree.files[0].path,'utf8')!=='fixture')throw new Error('Temporary fixture changed');
    fixtures.push({root,files:[{path:tree.files[0].path,bytes:7,sha256:await hash(tree.files[0].path)}],state:'PRESENT_CLEANUP_BLOCKED_BY_EXECUTION_POLICY',purpose:'Owned isolated ACL test, not product or recovery data'});
  }
  const id=crypto.randomUUID(),at=new Date().toISOString();
  const audit={id,kind:'DESKTOP_DEPENDENCY_ACL_TOOLING_HOLD',at,plan_id:plan.id,hold_id:hold.id,state:'BLOCKED_HOST_PRIVILEGE_AND_EXECUTION_POLICY',authority:'User approved ACL backup/repair on four rehearsal roots, followed by the previously approved cleanup.',candidate_files_confirmed_present:plan.files.length,candidate_acl_writes:0,deleted_candidate_files:0,deleted_candidate_bytes:0,remote_server_operations:0,root_acl_snapshot:snapshot,temporary_test_remnants:fixtures,validation:{pure_acl_assertions_passed:15,cleanup_assertions_passed:51,node_tests_passed:20,filesystem_acl_test:'FAILED_MISSING_SE_SECURITY_PRIVILEGE',actual_repair_started:false,deletion_started:false},reason:'Isolated temporary Set-Acl failed with missing SeSecurityPrivilege. An alternate test command and temporary fixture deletion command were rejected by tool execution policy; neither was run. No privilege elevation or alternate mutation mechanism attempted.',next_action:'Use an administrator PowerShell 7 on the development PC for the isolated filesystem ACL test and review its complete result before any real ACL repair. Preserve the original unresolved HOLD; no automatic retry.'};
  audit.tooling=await Promise.all(['repair-dependency-acl.ps1','repair-dependency-acl.test.ps1','check-dependency-links.cjs','remove-dependency-cleanup.ps1','manage-verification-files.cjs'].map(async source=>({source,sha256:await hash(path.join(repo,'scripts',source))})));
  audit.validation.read_only_whatif={state:'PASS',original_acl_records:82283,preserved_boundary_records:8009,files_hashed:74664,directories_checked:7619,filesystem_acl_apply_test_passed:false};
  if(await hash(indexPath)!==original)throw new Error('Concurrent registry change');
  index.audits.push(audit);index.history.push({at,kind:audit.kind,audit_id:id,plan_id:plan.id,state:audit.state,deleted_files:0,deleted_bytes:0,acl_writes:0});index.updated_at=at;
  save(index);console.log(JSON.stringify({id,state:audit.state,candidate_files_confirmed_present:plan.files.length,deleted_files:0,acl_writes:0,temporary_test_remnants:fixtures.length,index_sha256:await hash(indexPath)}));
}
async function recordDependencyAclFixturePass(expectedHash) {
  plain(indexPath);const original=await hash(indexPath);
  if(original!==expectedHash)throw new Error('External registry hash differs');
  const index=readIndexForUpdate();assertMigrationStates(index);
  if(index.host!==os.hostname()||os.hostname()!=='DESKTOP-SS5CURC'||index.workspace!==repo)throw new Error('Development host mismatch');
  const audit=index.audits.find(a=>a.id==='efdb5ead-0f84-4ee9-b0b9-44d063078981');
  const hold=index.audits.find(a=>a.id==='6f4737da-d677-4cb1-b919-d79f48bd991d');
  const plan=index.audits.find(a=>a.id==='31bd411f-0c64-469c-91ed-f5c3acae335f');
  if(!audit||audit.operator_fixture_report||!hold||hold.state!=='HOLD_ACL_TRUST_UNRESOLVED'||!plan||plan.cleanup||index.audits.some(a=>a.kind==='DESKTOP_DEPENDENCY_ACL_REPAIR'))throw new Error('Unexpected or already recorded repair state');
  const tooling=[];
  for(const source of ['repair-dependency-acl.test.ps1','repair-dependency-acl.ps1']){
    const actual=await hash(path.join(__dirname,source)),pin=audit.tooling.find(t=>t.source===source);
    if(!pin||pin.sha256!==actual)throw new Error('Tested ACL tooling has changed');
    tooling.push({source,sha256:actual});
  }
  const snapshot=JSON.parse(execFileSync('pwsh.exe',['-NoLogo','-NoProfile','-File',path.join(__dirname,'read-dependency-acl.ps1')],{encoding:'utf8',windowsHide:true,timeout:60000,maxBuffer:2e6}));
  if(snapshot.roots.length!==8||snapshot.roots.some(r=>!hold.snapshot.roots.some(old=>old.id===r.id&&old.path===r.path&&old.sddl===r.sddl)))throw new Error('Root ACL has changed; reconcile separately');
  const at=new Date().toISOString();
  audit.operator_fixture_report={received_at:at,source:'User-pasted console output; not independently executed by this agent',output:'[PASS] 22 ACL tests; PureOnly=False; no managed candidates or registry changed.',assertions_passed:22,pure_only:false,tooling,current_roots_match_original_hold:true,scope:'Isolated temporary fixture only; no actual repair or deletion completion claimed'};
  audit.next_action='Run the pinned ACL repair helper in the operator administrator PowerShell 7 session using the new external registry hash. Preserve the original ACL HOLD until the actual repair completes; deletion is a separate preflight/execution.';
  index.history.push({at,kind:'USER_REPORTED_ACL_FIXTURE_PASS',audit_id:audit.id,plan_id:plan.id,assertions_passed:22,acl_writes_to_candidates:0,deleted_files:0,deleted_bytes:0,remote_server_operations:0});index.updated_at=at;
  if(await hash(indexPath)!==original)throw new Error('Concurrent registry change');
  save(index);console.log(JSON.stringify({recorded_user_report:true,assertions:22,root_acls_unchanged:true,actual_repair_started:false,deletion_started:false,index_sha256:await hash(indexPath)}));
}
async function recordDependencyDeleteHandoff(expectedHash) {
  plain(indexPath);const original=await hash(indexPath);
  if(original!==expectedHash)throw new Error('External registry hash differs');
  const index=readIndexForUpdate();assertMigrationStates(index);
  if(index.host!==os.hostname()||os.hostname()!=='DESKTOP-SS5CURC'||index.workspace!==repo)throw new Error('Development host mismatch');
  const plan=index.audits.find(a=>a.id==='31bd411f-0c64-469c-91ed-f5c3acae335f');
  const repair=index.audits.find(a=>a.id==='94a8366c-d152-4211-9d7a-0774715c1e78');
  if(!plan||plan.cleanup||!repair||repair.state!=='COMPLETE'||repair.direct_acl_writes!==4||repair.inherited_entries_verified!==82283||repair.backup_records.length!==82283||index.audits.some(a=>a.kind==='DESKTOP_DEPENDENCY_DELETE_HANDOFF'))throw new Error('Unexpected or already recorded cleanup state');
  const rootMap=new Map(plan.roots.map(r=>[r.id,r.root]));
  let present=0,kept=0,anchors=0;
  for(const record of plan.files){const full=path.join(rootMap.get(record.root_id),...record.relative.split('/'));if(!fs.lstatSync(full).isFile())throw new Error('Candidate missing or changed type');present++;}
  for(const record of plan.keep_files){if(await hash(path.join(plan.keep_root,...record.relative.split('/')))!==record.sha256)throw new Error('Recovery file changed');kept++;}
  for(const record of plan.source_anchors){if(await hash(record.path)!==record.sha256)throw new Error('Source/package witness changed');anchors++;}
  const snapshot=JSON.parse(execFileSync('pwsh.exe',['-NoLogo','-NoProfile','-File',path.join(__dirname,'read-dependency-acl.ps1')],{encoding:'utf8',windowsHide:true,timeout:60000,maxBuffer:2e6}));
  if(snapshot.roots.length!==8||snapshot.roots.some(r=>rootMap.get(r.id)!==r.path||r.outside_writers.length))throw new Error('Root ACL trust differs');
  if(present!==152043||kept!==4092||anchors!==12)throw new Error('Approved counts differ');
  const id=crypto.randomUUID(),at=new Date().toISOString();
  const audit={id,kind:'DESKTOP_DEPENDENCY_DELETE_HANDOFF',at,plan_id:plan.id,repair_id:repair.id,state:'OPERATOR_EXECUTION_PENDING_FULL_PREFLIGHT',candidate_files_confirmed_present:present,recovery_hashes_verified:kept,source_anchor_hashes_verified:anchors,root_acl_snapshot:snapshot,whatif:{state:'CANCELLED_READ_ONLY_BY_OPERATOR_AGENT',last_reported_candidate_verification_count:33087,full_preflight_passed:false,registry_hash_unchanged_after_cancellation:original,reason:'Avoid repeating the lengthy full preflight twice. The actual deletion helper still performs every complete preflight check before any deletion. Ctrl+C stopped only the agent-owned WhatIf process and released its handles.'},deleted_files:0,deleted_bytes:0,acl_writes:0,remote_server_operations:0,next_action:'Operator runs the exact deletion helper using the new external registry hash. No check is skipped: it must complete scope, all candidate hashes/metadata/ACL/streams, recovery, source and use checks before journaling/deletion. Stop on HOLD; no automatic retry.'};
  audit.tooling=await Promise.all(['remove-dependency-cleanup.ps1','remove-dependency-cleanup.test.ps1'].map(async source=>({source,sha256:await hash(path.join(__dirname,source))})));
  if(await hash(indexPath)!==original)throw new Error('Concurrent registry change');
  index.audits.push(audit);index.history.push({at,kind:audit.kind,audit_id:id,plan_id:plan.id,state:audit.state,deleted_files:0,deleted_bytes:0,acl_writes:0});index.updated_at=at;
  save(index);console.log(JSON.stringify({id,state:audit.state,candidate_files_present:present,recovery_hashes_verified:kept,source_anchor_hashes_verified:anchors,full_preflight_passed:false,deleted_files:0,index_sha256:await hash(indexPath)}));
}
if(require.main===module) {
  const command=process.argv[2];
  Promise.resolve().then(()=>command==='record-dependency-delete-handoff'?recordDependencyDeleteHandoff(process.argv[3]):command==='record-dependency-acl-fixture-pass'?recordDependencyAclFixturePass(process.argv[3]):command==='record-dependency-acl-tooling-hold'?recordDependencyAclToolingHold(process.argv[3]):command==='record-dependency-acl-hold'?recordDependencyAclHold(process.argv[3]):command==='audit-build-dependencies'?auditBuildDependencies():command==='audit-build-checkout'?auditBuildCheckout():command==='scan'?scan():command==='plan'?planExact(process.argv.slice(3)):command==='plan-duplicates'?planDuplicateDirs():command==='recover-journal'?recoverJournal():command==='prepare-desktop-migration'?prepareDesktopMigration():command==='prepare-transfer-migration'?prepareTransferMigration():command==='prepare-release-migration'?prepareReleaseMigration():command==='prepare-transfer-batches'?prepareTransferBatchMigrations():command==='verify'?verify():Promise.reject(new Error('Use a documented inventory, planning, audit or verification command'))).catch(e=>{console.error(e.message);process.exitCode=1;});
}
module.exports={inside,plain,walk,hash,sourceCatalog,desktopEvidenceRoot,assertMigrationStates,assertReviewedCleanupStates,archiveDuplicateRule,releaseRetention,releaseDestinationName,transferBatchSpecs,buildCheckoutClass,distArchiveRecords,stageExtractionRecords,attestationExtractionRecords,isolatedTestCacheSpecs,isolatedTestCacheRecords,buildIntermediateRecords,chromeTestProfileSpecs,chromeCacheUnit,chromeTestCacheRecords};
