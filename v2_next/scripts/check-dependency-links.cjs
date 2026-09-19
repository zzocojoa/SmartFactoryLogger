// Read only: ACL inheritance must not touch an alternate hard-linked path outside the four roots.
const fs=require('node:fs'),path=require('node:path'),os=require('node:os');
const {plain,walk,hash}=require('./manage-verification-files.cjs');
const {targets,child}=require('./plan-dependency-cleanup.cjs');
async function main(){
const repo=path.resolve(__dirname,'..'),index=JSON.parse(fs.readFileSync(path.join(repo,'verification-files.local.json')));
const plan=index.audits.find(a=>a.id==='31bd411f-0c64-469c-91ed-f5c3acae335f');
if(os.hostname()!=='DESKTOP-SS5CURC'||index.workspace!==repo)throw Error('Host mismatch');
const selected=targets(plan.checkout,path.join(repo,'.tmp/dep-428c970f-1f0e-4127-802c-7b4ba9d621c0')).filter(r=>r.id.startsWith('test-'));
let files=0,dirs=0;
for(const root of selected){
  plain(root.root);const tree=walk(root.root);if(tree.links.length||tree.errors.length)throw Error('Linked or incomplete tree');
  const expected=new Map(plan.files.filter(f=>f.root_id===root.id).map(f=>[child(root.root,f.relative),f]));
  if(tree.files.length!==expected.size)throw Error('File set changed');
  for(const f of tree.files){
    const record=expected.get(f.path),s=fs.lstatSync(f.path,{bigint:true});
    if(!record||s.nlink!==1n)throw Error('Hard link or unexpected file');
    if(s.size!==BigInt(record.bytes)||s.mtimeNs!==BigInt(record.mtime_ns)||s.birthtimeNs!==BigInt(record.birthtime_ns)||(await hash(f.path))!==record.sha256)throw Error('Content or file times changed');
    expected.delete(f.path);files++;
  }
  dirs+=tree.dirs.length;
}
if(files!==74664||dirs!==7619)throw Error('Approved scope differs');
console.log(JSON.stringify({result:'SINGLE_LINK_EXACT_TREE_CONTENT_PASS',files,directories:dirs,hashes_verified:files,writes:0}));
}
main().catch(error=>{console.error(error.message);process.exitCode=1;});
