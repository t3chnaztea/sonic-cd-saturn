'use strict';
// Private-input integration runner. Each run owns a new workspace under build/.
const fs=require('node:fs'),path=require('node:path');
const crypto=require('node:crypto'),{pathToFileURL}=require('node:url');
const root=path.resolve(__dirname,'..');
const hash=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const [outArg,runtimeArg,pyodideArg]=process.argv.slice(2);
const extra=process.argv.slice(5),options={};
for(let i=0;i<extra.length;i+=2){if(!['--seed','--script','--recipe','--site'].includes(extra[i])||!extra[i+1])throw Error('Invalid integration option');options[extra[i]]=extra[i+1];}
if(!outArg||!runtimeArg||!pyodideArg)throw Error('Usage: node tools/test-patcher-pipeline.cjs NEW_BUILD_DIR RUNTIME_DIR PYODIDE_DIR');
const out=path.resolve(outArg),runtime=path.resolve(runtimeArg),pyDir=path.resolve(pyodideArg),stage=path.join(out,'project');
if(!out.startsWith(path.join(root,'build')+path.sep)||fs.existsSync(out))throw Error('Output must be a new directory under build/.');
fs.mkdirSync(stage,{recursive:true});
fs.writeFileSync(path.join(out,'process.json'),JSON.stringify({pid:process.pid,status:'running'})+'\n');
if(options['--seed']){
 const seed=path.resolve(options['--seed']);
 if(!seed.startsWith(path.join(root,'build')+path.sep))throw Error('Seed fixtures must be under build/');
 fs.cpSync(path.join(seed,'project'),stage,{recursive:true,dereference:false,
  filter:source=>!(options['--recipe']&&source===path.join(seed,'project/program/ponesound.bin'))});
}
const codeRoot=options['--site']?path.resolve(options['--site']):root;
if(options['--site']&&!codeRoot.startsWith(path.join(root,'build')+path.sep))throw Error('Site must be under build/');
const plan=JSON.parse(fs.readFileSync(path.join(codeRoot,'web/patcher/pipeline-lock.json'),'utf8'));
const files=new Set(plan.project.map(row=>row.path));
for(const name of ['tools/native.py','tools/browser_ctypes.py'])files.add(name);
for(const name of files){
 const pin=plan.project.find(row=>row.path===name),source=path.join(codeRoot,name);
 if(!pin||hash(source)!==pin.sha256||fs.statSync(source).size!==pin.bytes)throw Error('Site code changed: '+name);
 fs.mkdirSync(path.dirname(path.join(stage,name)),{recursive:true});fs.copyFileSync(source,path.join(stage,name));
}
for(const name of ['assets/generated','assets/private','build/retail','dist','cd','program'])fs.mkdirSync(path.join(stage,name),{recursive:true});
for(const name of ['sonic.bin','sonic.cue',...options['--recipe']?[]:['sonic.iso']])fs.copyFileSync(path.join(root,'build/retail',name),path.join(stage,'build/retail',name));
fs.copyFileSync(path.join(root,'assets/private/bios_CD_U.bin'),path.join(stage,'assets/private/bios_CD_U.bin'));
if(!options['--recipe'])fs.copyFileSync(path.join(root,'build/sound-driver/driver.bin'),path.join(stage,'program/ponesound.bin'));
if(options['--recipe']){
 const recipe=path.resolve(options['--recipe']);
 if(!recipe.startsWith(path.join(root,'build')+path.sep))throw Error('Recipe must be a local build candidate');
 const data=fs.readFileSync(recipe),length=data.readUInt32LE(8),manifest=JSON.parse(data.subarray(12,12+length)),literals=data.subarray(12+length);
 if(data.subarray(0,8).toString()!=='SCSP082\n'||manifest.format!==2||crypto.createHash('sha256').update(literals).digest('hex')!==manifest.construction.payload_sha256)throw Error('Invalid recipe candidate');
 fs.writeFileSync(path.join(stage,'program/construction.json'),JSON.stringify(manifest.construction));
 fs.writeFileSync(path.join(stage,'program/literals.bin'),literals);
}
const sourceCommands=plan.commands
  .filter(c=>!options['--script']||options['--script'].split(',').includes(c.script));
if(!sourceCommands.length)throw Error('No selected converter in build.sh');
const diagnostic=!!(options['--seed']||options['--script']);
fs.writeFileSync(path.join(out,'run.json'),JSON.stringify({mode:diagnostic?'diagnostic':'fresh-full',options},null,2)+'\n');
function snapshot(dir=stage,found={}){
 for(const e of fs.readdirSync(dir,{withFileTypes:true})){
  const p=path.join(dir,e.name);if(e.isSymbolicLink())continue;
  if(e.isDirectory())snapshot(p,found);else{const s=fs.statSync(p);found[path.relative(stage,p)]=`${s.size}:${s.mtimeMs}:${s.ctimeMs}`;}
 }
 return found;
}
function mountRO(py,host,target){
 const FS=py.FS,N=FS.filesystems.NODEFS,ro={...N,node_ops:{...N.node_ops},stream_ops:{...N.stream_ops}},deny=()=>{throw new FS.ErrnoError(30);};
 for(const k of ['setattr','mknod','rename','unlink','rmdir','symlink'])ro.node_ops[k]=deny;
 ro.stream_ops.write=deny;ro.stream_ops.open=s=>{if((s.flags&3)!==0||(s.flags&(64|512|1024)))deny();return N.stream_ops.open(s);};
 ro.createNode=(p,n,mode,d)=>{const a=N.createNode(p,n,mode,d);a.node_ops=ro.node_ops;a.stream_ops=ro.stream_ops;return a;};
 ro.mount=m=>ro.createNode(null,'/',N.getMode(m.opts.root),0);
 ro.node_ops.lookup=(p,n)=>ro.createNode(p,n,N.getMode(path.join(N.realPath(p),n)),0);
 FS.mkdirTree(target);FS.mount(ro,{root:host},target);
}
(async()=>{
 globalThis.fetch=async()=>{throw Error('Network disabled during local pipeline verification');};
 const {loadPyodide}=await import(pathToFileURL(path.join(pyDir,'pyodide.mjs')));
 const py=await loadPyodide({indexURL:pyDir+path.sep});await py.loadPackage('pillow');
  py.setDebug(true);
 const FS=py.FS;FS.mkdir('/project');FS.mount(FS.filesystems.NODEFS,{root:stage},'/project');
 const reads=new Set(),open=FS.open;
 FS.open=function(request,...args){
  const stream=open.call(FS,request,...args);
  if(typeof request==='string'){
   const name=path.posix.resolve(FS.cwd(),request);
   if(['/project/.deps/','/project/src/','/project/.toolchain/','/project/tools/'].some(p=>name.startsWith(p)))reads.add(name.slice('/project/'.length));
  }
  return stream;
 };
 // Match the site: only reference files in the pinned lock exist here.
 for(const row of plan.references){
  const source=path.join(root,row.path),target=path.join(stage,row.path);
  if(hash(source)!==row.sha256||fs.statSync(source).size!==row.bytes)throw Error('Pinned reference changed: '+row.path);
  fs.mkdirSync(path.dirname(target),{recursive:true});fs.copyFileSync(source,target);
 }
 const cue=fs.realpathSync(path.join(root,'assets/private/sonic-cd-japan.cue'));
 mountRO(py,path.dirname(cue),'/discs/jp');if(!FS.analyzePath('/project/assets/private/sonic-cd-japan.cue').exists)FS.symlink('/discs/jp/'+path.basename(cue),'/project/assets/private/sonic-cd-japan.cue');
 const names=['genesis','sonic','fmv','iso'],binaries={},modules={},factories={};
 for(const name of names){binaries[name]=fs.readFileSync(path.join(runtime,name+'.wasm'));modules[name]=new WebAssembly.Module(binaries[name]);factories[name]=require(path.join(runtime,name+'.js'));}
 const ffDir=path.join(codeRoot,'web/patcher/vendor/ffmpeg');
 globalThis.self={location:{href:'file://'+path.join(ffDir,'ffmpeg-core.js')}};
 binaries.ffmpeg=fs.readFileSync(path.join(ffDir,'ffmpeg-core.wasm'));modules.ffmpeg=new WebAssembly.Module(binaries.ffmpeg);factories.ffmpeg=require(path.join(ffDir,'ffmpeg-core.js'));
 FS.mkdirTree('/project/browser');
 for(const name of ['native.js','pyfs.js','audio.js'])FS.writeFile('/project/browser/'+name,fs.readFileSync(path.join(root,'web/patcher',name)));
 for(const name of ['genesis.js','genesis.wasm'])FS.writeFile('/project/browser/'+name,fs.readFileSync(path.join(runtime,name)));
 for(const name of ['ffmpeg-core.js','ffmpeg-core.wasm'])FS.writeFile('/project/browser/'+name,fs.readFileSync(path.join(ffDir,name)));
 const {mount}=require(path.join(codeRoot,'web/patcher/pyfs.js')),{pastFade}=require(path.join(codeRoot,'web/patcher/audio.js'));
 const locks=JSON.parse(fs.readFileSync(path.join(root,'sources.lock.json'),'utf8'));
 const commits=Object.fromEntries(Object.entries(locks).filter(([,v])=>v.commit).map(([k,v])=>[k,v.commit]));
 const backend=require(path.join(codeRoot,'web/patcher/native.js')).create({FS,binaries,modules,factories,mount,pastFade,commits});backend.resetGenesis();
 py.globals.set('_native_backend',backend);
 py.globals.set('_browser_core_sha',hash(path.join(runtime,'genesis.wasm')));
 py.runPython(`import os,sys,runpy,traceback
os.chdir('/project')
sys.path.insert(0,'/project/tools')
os.environ['SCD_QA_MAX_WORKERS']='1'
os.environ['SCD_QA_MAX_EMULATORS']='1'
os.environ['SCD_BROWSER_CORE_SHA256']=_browser_core_sha
import native
${options['--recipe']?'':'native.install(_native_backend)'}
`);
 if(options['--recipe']){
  // Reproduce the browser bootstrap. No pre-extracted U.S. ISO is seeded.
  const bootstrap=fs.readFileSync(path.join(codeRoot,plan.bootstrap.path),'utf8');
  if(hash(path.join(codeRoot,plan.bootstrap.path))!==plan.bootstrap.sha256)throw Error('Bootstrap changed');
  py.runPython(bootstrap);
  py.runPython(`initialize(_native_backend,json.loads(Path('/project/program/construction.json').read_text()),_browser_core_sha)`);
 }
 const results=[];
 for(let i=0;i<sourceCommands.length;i++){
  const command=sourceCommands[i],before=snapshot(),log=[],start=performance.now();
  fs.writeFileSync(path.join(out,'pending.json'),JSON.stringify({index:i,script:command.script,status:'pending'})+'\n');
  py.setStdout({batched:s=>log.push(s)});py.setStderr({batched:s=>log.push(s)});
  py.globals.set('_script',command.script);py.globals.set('_args',py.toPy(command.args));
  let status='PASS',error=null;
  try{py.runPython(`_rc,_stdout,_stderr=native._python([_script,*_args],'/project')
print(_stdout,end='')
print(_stderr,end='',file=sys.stderr)
if _rc: raise SystemExit(_rc)
`);}catch(e){status='FAIL';error=String(e);log.push(error);}
  const after=snapshot(),outputs=[];
  for(const p of Object.keys(after))if(before[p]!==after[p]){
   const actual=path.join(stage,p),reference=path.join(root,p),digest=hash(actual),native=fs.existsSync(reference)&&fs.statSync(reference).isFile()?hash(reference):null;
   outputs.push({file:p,bytes:fs.statSync(actual).size,sha256:digest,native_sha256:native,identical:native===null?null:digest===native});
  }
  results.push({...command,status,error,wall_seconds:(performance.now()-start)/1000,process_peak_rss_bytes:process.resourceUsage().maxRSS*1024,outputs});
  fs.writeFileSync(path.join(out,`${String(i+1).padStart(2,'0')}-${path.basename(command.script)}.log`),log.join('\n')+'\n');
  fs.writeFileSync(path.join(out,'results.json'),JSON.stringify(results,null,2)+'\n');
  fs.writeFileSync(path.join(out,'source-files-used.json'),JSON.stringify([...reads].sort(),null,2)+'\n');
  console.log(`${status}: pipeline ${i+1}/${sourceCommands.length} ${command.script}; ${outputs.length} outputs`);
  fs.writeFileSync(path.join(out,'pending.json'),JSON.stringify({index:i,script:command.script,status:status.toLowerCase()})+'\n');
 }
 const passed=results.filter(r=>r.status==='PASS').length;
 console.log(`${diagnostic?'DIAGNOSTIC':passed===results.length?'PASS':'FAIL'}: browser conversion pipeline; ${passed}/${results.length} invocations`);
 if(passed!==results.length)process.exitCode=1;
 fs.writeFileSync(path.join(out,'process.json'),JSON.stringify({pid:process.pid,status:passed===results.length?'passed':'failed'})+'\n');
})().catch(e=>{console.error(e.stack||e);process.exitCode=1;});
