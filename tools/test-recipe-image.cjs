'use strict';
// Final Node assembly proof. Fresh runs must execute the complete browser plan.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {File}=require('node:buffer'),crypto=require('node:crypto');
const engine=require('../web/patcher/engine.js'),release=require('../web/patcher/release.js');
const root=path.resolve(__dirname,'..');
const [recipeArg,projectArg,outArg]=process.argv.slice(2);
const diagnostic=process.argv[5]==='--diagnostic';
if(process.argv.length>(diagnostic?6:5))throw Error('Unexpected image-test argument');
if(!recipeArg||!projectArg||!outArg)throw Error('Usage: node tools/test-recipe-image.cjs RECIPE.scsp FRESH_RUN/project NEW_BUILD_RECEIPT_DIR');
const project=path.resolve(projectArg),out=path.resolve(outArg),parent=path.dirname(project);
if(![project,out].every(p=>p.startsWith(path.join(root,'build')+path.sep))||fs.existsSync(out))throw Error('Use a completed private run and a new receipt directory under build/');
assert.equal(JSON.parse(fs.readFileSync(path.join(parent,'run.json'),'utf8')).mode,diagnostic?'diagnostic':'fresh-full');
assert.equal(JSON.parse(fs.readFileSync(path.join(parent,'process.json'),'utf8')).status,'passed');
const stages=JSON.parse(fs.readFileSync(path.join(parent,'results.json'),'utf8'));
const commands=JSON.parse(fs.readFileSync(path.join(root,'web/patcher/pipeline-lock.json'),'utf8')).commands;
if(diagnostic)assert.equal(stages.at(-1).script,'tools/package.py');
else assert.deepEqual(stages.map(({script,args})=>({script,args})),commands);
assert(stages.every(s=>s.status==='PASS'));
if(!globalThis.crypto)globalThis.crypto=crypto.webcrypto;
async function sha(blob){const hash=crypto.createHash('sha256');for await(const chunk of blob.stream())hash.update(chunk);return hash.digest('hex');}
async function main(){
 if(typeof fs.openAsBlob!=='function')throw Error('Node 22 with file-backed Blobs is required');
 const bundle=await fs.openAsBlob(path.resolve(recipeArg)),{data}=await engine.inspect(bundle,release);
 const jp=fs.realpathSync(path.join(root,'assets/private/sonic-cd-japan.cue'));
 const inputs=[];
 for(const row of data.sources){
  const file=row.role==='jp'?path.join(path.dirname(jp),row.name):path.join(root,row.role==='us'?'build/retail':'assets/private',row.name);
  inputs.push({role:row.role,file:new File([await fs.openAsBlob(file)],row.name)});
 }
 let bytes=0;
 for(const row of data.construction.iso_layout.files){
  const file=await fs.openAsBlob(path.join(project,row.source));
  assert.equal(file.size,row.bytes);assert.equal(await sha(file),row.sha256);bytes+=file.size;
 }
 const output=new Map();
 for(const row of data.derivations)output.set(row.name,await fs.openAsBlob(path.join(project,row.name)));
 const result=await engine.apply(bundle,inputs,release,()=>{},async()=>output);
 assert.equal(await sha(result.bin),release.binSha256);assert.equal(await sha(result.cue),release.cueSha256);
 fs.mkdirSync(out);
 fs.writeFileSync(path.join(out,'report.json'),JSON.stringify({status:'PASS',recipe_sha256:await sha(bundle),
  fresh_commands:diagnostic?0:stages.length,diagnostic,cd_files:data.construction.iso_layout.files.length,cd_bytes:bytes,
  bin_sha256:release.binSha256,cue_sha256:release.cueSha256,hardware_tested:false},null,2)+'\n');
 console.log('PASS: Node recipe assembly; '+(diagnostic?'diagnostic Pyodide packaging':stages.length+' fresh Pyodide invocations')+'; exact accepted '+release.version+' BIN/CUE');
}
main().catch(error=>{console.error(error);process.exitCode=1;});
