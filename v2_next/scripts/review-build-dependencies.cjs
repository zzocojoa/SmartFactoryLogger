// Metadata/content audit only. Never execute historical code, install, fetch, or delete.
const fs=require('node:fs');
const path=require('node:path');
const os=require('node:os');
const crypto=require('node:crypto');
const {execFileSync}=require('node:child_process');
const slash=p=>p.split(path.sep).join('/');

function parseRecord(text) {
  const rows=[];let row=[],field='',quoted=false,closed=false;
  const endField=()=>{row.push(field);field='';closed=false;};
  const endRow=()=>{endField();if(row.length!==1||row[0]!==''){if(row.length!==3)throw new Error('Invalid RECORD column count');rows.push(row);}row=[];};
  for(let i=0;i<text.length;i++){
    const c=text[i];
    if(quoted){if(c==='"'){if(text[i+1]==='"'){field+='"';i++;}else{quoted=false;closed=true;}}else field+=c;continue;}
    if(c===',')endField();
    else if(c==='\n'||c==='\r'){if(c==='\r'&&text[i+1]==='\n')i++;endRow();}
    else if(c==='"'&&!field&&!closed)quoted=true;
    else {if(closed||c==='"')throw new Error('Invalid RECORD quoting');field+=c;}
  }
  if(quoted)throw new Error('Unclosed RECORD field');
  if(field||row.length||closed)endRow();
  return rows;
}
function recordPath(root,site,name) {
  if(!name||/[\\:\0]/.test(name)||path.posix.isAbsolute(name))throw new Error('Invalid RECORD path');
  const file=path.resolve(site,...name.split('/'));
  if(!file.toLowerCase().startsWith(path.resolve(root).toLowerCase()+path.sep))throw new Error('RECORD leaves environment');
  return file;
}
function platformExcluded(item,platform,arch) {
  const allows=(values,value)=>!values||(!values.includes('!'+value)&&(!values.some(v=>!v.startsWith('!'))||values.includes(value)));
  return !allows(item.os,platform)||!allows(item.cpu,arch);
}
function compareNode(lock,hidden,installed,platform='win32',arch='x64') {
  const result={locked_packages:0,matching_versions:0,absent_optional_other_platform:[],problems:[],missing_integrity:[],install_scripts:[]};
  for(const [key,item] of Object.entries(lock.packages)){
    if(!key)continue;result.locked_packages++;
    if(!item.integrity)result.missing_integrity.push(key);
    if(item.hasInstallScript)result.install_scripts.push({path:key,version:item.version});
    const actual=installed[key];
    if(!actual){
      if(item.optional&&platformExcluded(item,platform,arch))result.absent_optional_other_platform.push(key);
      else result.problems.push({path:key,reason:'MISSING_REQUIRED_OR_CURRENT_PLATFORM_PACKAGE'});
    }else if(actual.version!==item.version)result.problems.push({path:key,reason:'INSTALLED_VERSION_DIFFERS',expected:item.version,actual:actual.version});
    else result.matching_versions++;
  }
  for(const [key,item] of Object.entries(hidden.packages)){
    const expected=lock.packages[key];
    if(!expected||item.version!==expected.version||item.integrity!==expected.integrity)result.problems.push({path:key,reason:'HIDDEN_LOCK_DIFFERS'});
    if(!installed[key])result.problems.push({path:key,reason:'HIDDEN_LOCK_PACKAGE_MISSING'});
  }
  for(const key of Object.keys(installed))if(!hidden.packages[key])result.problems.push({path:key,reason:'HIDDEN_LOCK_ENTRY_MISSING'});
  return result;
}
function gridPatchState(text) {
  return Object.entries({GRID_CELL_HEIGHT:20,GRID_CELL_VMARGIN:4,GRID_COLUMN_COUNT:60}).map(([name,expected])=>{
    const values=[...text.matchAll(new RegExp('const '+name+' = (\\d+);','g'))].map(m=>Number(m[1]));
    return {name,expected,values,matches:values.length>0&&values.every(v=>v===expected)};
  });
}
async function review(index,helpers) {
  const {plain,walk,hash}=helpers;
  if(os.hostname()!=='DESKTOP-SS5CURC')throw new Error('Development host required');
  const checkout=plain(path.join(os.homedir(),'Desktop','SmartFactoryLogger_Builds','spot-tcp-connection-reuse-remediation_bfd9be7','source'));
  const project=path.join(checkout,'v2_next');
  const classification=(index.audits||[]).find(a=>a.id==='48c1e9fe-4708-43d9-bf67-876199d9ffa8');
  if(!classification||classification.checkout.toLowerCase()!==checkout.toLowerCase())throw new Error('Original checkout audit missing');
  const git=args=>execFileSync('git',['--no-optional-locks','-c','core.fsmonitor=false','-C',checkout,...args],{encoding:'utf8',timeout:60000,maxBuffer:30e6});
  const head=git(['rev-parse','HEAD']).trim(),status=()=>git(['status','--porcelain=v1','-z','--untracked-files=all']);
  if(head!=='bfd9be785f7a87aa4150445945861a54bca98f33'||status())throw new Error('Historical source identity/status changed');
  const gitIndexHash=await hash(path.join(checkout,'.git/index'));
  const anchors=new Map();
  async function read(file){
    plain(file);const before=await hash(file),data=fs.readFileSync(file);
    if(crypto.createHash('sha256').update(data).digest('hex').toUpperCase()!==before)throw new Error('Metadata changed while reading');
    anchors.set(file,before);return data.toString('utf8');
  }
  const paths=['node_modules','frontend/node_modules','backend/.venv','backend/browsers'];
  const inventories=[],groups=[];
  for(const relative of paths){
    const root=plain(path.join(project,relative)),inventory=walk(root);
    if(inventory.links.length||inventory.errors.length)throw new Error('Incomplete dependency inventory');
    inventories.push(inventory);groups.push({relative,files:inventory.files.length,bytes:inventory.files.reduce((n,f)=>n+f.bytes,0),decision:'PRESERVE_PENDING_REINSTALL_VERIFICATION'});
  }
  const currentFiles=new Map(inventories.flatMap(i=>i.files).map(f=>[slash(path.relative(checkout,f.path)),f]));
  const original=classification.files.filter(f=>f.classification==='CANDIDATE_REINSTALLABLE_DEPENDENCY');
  if(currentFiles.size!==original.length||original.some(f=>{const a=currentFiles.get(f.relative);return !a||a.bytes!==f.bytes||a.mtime_ms!==f.mtime_ms;}))throw new Error('Dependency inventory differs from reviewed baseline');
  console.log('[DEPENDENCIES] Fixed inventory matched; reading Node manifests.');
  const node=[];
  for(const relative of ['', 'frontend']){
    const dir=path.join(project,relative),pkg=JSON.parse(await read(path.join(dir,'package.json'))),lock=JSON.parse(await read(path.join(dir,'package-lock.json'))),hidden=JSON.parse(await read(path.join(dir,'node_modules/.package-lock.json'))),installed={};
    if(lock.lockfileVersion!==3||hidden.lockfileVersion!==3)throw new Error('Unexpected lock format');
    for(const field of ['dependencies','devDependencies','optionalDependencies']){
      const stable=value=>JSON.stringify(Object.entries(value||{}).sort(([a],[b])=>a.localeCompare(b)));
      if(stable(pkg[field])!==stable(lock.packages[''][field]))throw new Error('Root manifest and lock differ');
    }
    for(const key of new Set([...Object.keys(lock.packages),...Object.keys(hidden.packages)])){
      if(!key)continue;
      if(key.includes('\\')||!key.startsWith('node_modules/')||key.split('/').some(x=>!x||x==='..'||x==='.')||key.includes(':'))throw new Error('Invalid lock package path');
      const file=path.join(dir,key,'package.json');
      if(fs.existsSync(file))installed[key]=JSON.parse(await read(file));
    }
    node.push({relative:relative||'.',...compareNode(lock,hidden,installed),package_content_verified_against_tarballs:false,offline_cache_verified:false});
  }
  const patchScript='frontend/scripts/patch_grafana_scenes_grid.js';
  await read(path.join(project,patchScript));
  const patch=[];
  for(const file of ['frontend/node_modules/@grafana/scenes/dist/esm/packages/scenes/src/components/layout/grid/constants.js','frontend/node_modules/@grafana/scenes/dist/index.js'])patch.push({relative:file,constants:gridPatchState(await read(path.join(project,file)))});
  console.log('[DEPENDENCIES] Node versions checked; checking Python RECORD hashes.');
  const venv=path.join(project,'backend/.venv'),site=path.join(venv,'Lib/site-packages'),distributions=[],recordFiles=new Set(),digestCache=new Map();
  for(const name of fs.readdirSync(site).filter(n=>n.endsWith('.dist-info')).sort()){
    const dist=path.join(site,name),metadata=await read(path.join(dist,'METADATA'));
    const header=metadata.split(/\r?\n\r?\n/,1)[0];
    const packageName=/^Name: (.+)$/m.exec(header)?.[1].trim(),version=/^Version: (.+)$/m.exec(header)?.[1].trim();
    if(!packageName||!version)throw new Error('Python distribution identity missing');
    const rows=parseRecord(await read(path.join(dist,'RECORD'))),result={name:packageName,version,record_entries:rows.length,hashed_matches:0,unhashed:0,problems:[],direct_url_present:fs.existsSync(path.join(dist,'direct_url.json'))};
    for(const [relative,expected,size] of rows){
      const file=recordPath(venv,site,relative);recordFiles.add(file.toLowerCase());
      if(!fs.existsSync(file)){result.problems.push({relative,reason:'MISSING'});continue;}
      plain(file);const stat=fs.statSync(file);
      if(!stat.isFile())throw new Error('Non-file RECORD entry');
      if(size!==''&&(!/^\d+$/.test(size)||stat.size!==Number(size))){result.problems.push({relative,reason:'SIZE_DIFFERS'});continue;}
      if(!expected){result.unhashed++;continue;}
      if(!/^sha256=[A-Za-z0-9_-]{43}$/.test(expected)){result.problems.push({relative,reason:'UNSUPPORTED_RECORD_HASH'});continue;}
      if(!digestCache.has(file))digestCache.set(file,await hash(file));
      if(Buffer.from(digestCache.get(file),'hex').toString('base64url')!==expected.slice(7))result.problems.push({relative,reason:'HASH_DIFFERS'});else result.hashed_matches++;
    }
    distributions.push(result);
  }
  const requirements=[];
  for(const relative of ['backend/requirements.txt','backend/requirements-build.txt']){
    const lines=(await read(path.join(project,relative))).split(/\r?\n/);
    for(let i=0;i<lines.length;i++){
      const text=lines[i].trim();if(!text||text.startsWith('#')||text==='-r requirements.txt')continue;
      const match=/^([A-Za-z0-9_.-]+)(?:(==|>=)([A-Za-z0-9_.-]+))?$/.exec(text);
      if(!match)throw new Error('Unreviewed requirement syntax');
      requirements.push({source:relative,line:i+1,name:match[1],operator:match[2]||null,version:match[3]||null,exact:match[2]==='=='});
    }
  }
  const config=await read(path.join(venv,'pyvenv.cfg'));
  const python={version:/^version = (.+)$/m.exec(config)?.[1].trim(),base_interpreter_exists:fs.existsSync('C:\\Python312\\python.exe'),requirements,distributions,unrecorded_files:inventories[2].files.filter(f=>!recordFiles.has(f.path.toLowerCase())).map(f=>slash(path.relative(venv,f.path))),record_is_independent_trust_anchor:false,wheels_verified:false};
  const browserManifest=JSON.parse(await read(path.join(site,'playwright/driver/package/browsers.json')));
  const browsers=[];
  for(const name of fs.readdirSync(path.join(project,'backend/browsers')).filter(n=>n!=='.links')){
    const spec=browserManifest.browsers.find(b=>b.name.replaceAll('-','_')+'-'+b.revision===name);
    browsers.push({directory:name,manifest_match:!!spec,revision:spec?.revision||null,version:spec?.browserVersion||null,installation_marker:fs.existsSync(path.join(project,'backend/browsers',name,'INSTALLATION_COMPLETE'))});
  }
  const sources=[];
  for(const [relative,needle] of [['scripts/deploy.ps1','-m pip install'],['scripts/deploy.ps1','-m playwright install chromium'],['../.github/workflows/windows-release-artifact.yml','run: npm ci']]){
    const file=path.join(project,relative),lines=(await read(file)).split(/\r?\n/),line=lines.findIndex(x=>x.includes(needle))+1;
    if(!line)throw new Error('Installation source anchor missing');sources.push({relative:slash(path.relative(checkout,file)),line});
  }
  // Recheck metadata and scope before publishing. This is not an atomic snapshot or delete manifest.
  for(const [file,expected] of anchors)if(await hash(file)!==expected)throw new Error('Audit source changed');
  for(let i=0;i<paths.length;i++){
    const after=walk(path.join(project,paths[i])),before=new Map(inventories[i].files.map(f=>[f.path,f]));
    if(after.links.length||after.errors.length||after.files.length!==before.size||after.dirs.length!==inventories[i].dirs.length||after.files.some(f=>{const b=before.get(f.path);return !b||b.bytes!==f.bytes||b.mtime_ms!==f.mtime_ms;}))throw new Error('Dependency tree changed during review');
  }
  if(git(['rev-parse','HEAD']).trim()!==head||status()||await hash(path.join(checkout,'.git/index'))!==gitIndexHash)throw new Error('Checkout changed');
  return {id:crypto.randomUUID(),kind:'DESKTOP_BUILDS_DEPENDENCY_REVIEW',at:new Date().toISOString(),checkout,head,state:'REVIEWED_PRESERVE_NOT_DELETION_APPROVAL',groups,node,grid_patch:{script:patchScript,targets:patch},python,browsers,source_anchors:sources,read_file_hashes:[...anchors].map(([file,sha256])=>({relative:slash(path.relative(checkout,file)),sha256})),source_writes:0,deleted_files:0,moved_files:0,remote_server_operations:0,limitations:['Node package versions and lock metadata match checks do not prove installed package contents are unmodified; tarballs and lifecycle downloads were not compared.','Python RECORD is local metadata, not independently authenticated wheel provenance. Unhashed and unrecorded files are not integrity verified.','Browser revision names and installation markers do not prove browser file integrity or download availability.','Requirements are not a complete exact-version lock; installed versions are retained here as evidence, not a verified reinstall recipe.','No network, reinstall, build, operational process/reference, ACL or alternate-stream deletion check was performed. No deletion is authorized.']};
}
module.exports={parseRecord,recordPath,platformExcluded,compareNode,gridPatchState,review};
