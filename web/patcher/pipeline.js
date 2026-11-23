'use strict';
// User files are read-only Blob mounts. Only pinned GET requests are made.
const SonicPipeline = (() => {
  const base=new URL('.',self.location.href);
  const safe=p=>typeof p==='string'&&!p.startsWith('/')&&!/[\\\x00-\x1f]/.test(p)&&p.split('/').every(x=>x&&x!=='.'&&x!=='..');
  const digest=async data=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',data)),x=>x.toString(16).padStart(2,'0')).join('');
  async function get(url,expected,signal) {
    const response=await fetch(url,{method:'GET',credentials:'omit',redirect:'error',referrerPolicy:'no-referrer',signal});
    if(!response.ok)throw Error('A required patcher file is unavailable.');
    const bytes=new Uint8Array(await response.arrayBuffer());
    if(expected&&(bytes.length!==expected.bytes||await digest(bytes)!==expected.sha256))throw Error('A pinned patcher or reference file failed its checksum.');
    return bytes;
  }
  // Reference URLs are pinned by commit, so a verified body can be reused.
  // A cached body is hashed again before use. A mismatch deletes the entry and
  // the file is fetched again. Any Cache API failure falls back to plain fetch.
  const CACHE_NAME='sonic-cd-saturn-references-v1';
  async function openCache(){
    try{return self.caches?await self.caches.open(CACHE_NAME):null;}catch{return null;}
  }
  async function getReference(store,row,signal,count) {
    if(store){
      try{
        const hit=await store.match(row.url);
        if(hit){
          const bytes=new Uint8Array(await hit.arrayBuffer());
          if(bytes.length===row.bytes&&await digest(bytes)===row.sha256){count.hits++;return bytes;}
          await store.delete(row.url);
        }
      }catch{}
    }
    const bytes=await get(row.url,row,signal);
    if(store){
      try{await store.put(row.url,new Response(bytes.slice(),{status:200,headers:{'Content-Type':'application/octet-stream'}}));}catch{}
    }
    return bytes;
  }
  // Runs task on up to LIMIT rows at once. done receives results in row order,
  // so file writes and progress messages keep the sequential order. The first
  // failure aborts the open requests and is thrown after all workers stop.
  const LIMIT=12;
  async function pool(rows,task,done) {
    const results=new Array(rows.length),ready=new Uint8Array(rows.length),abort=new AbortController();
    let next=0,flushed=0,failed=false,failure;
    const stop=error=>{if(!failed){failed=true;failure=error;abort.abort();}};
    const worker=async()=>{
      while(!failed&&next<rows.length){
        const index=next++;
        try{
          results[index]=await task(rows[index],abort.signal);ready[index]=1;
          while(!failed&&flushed<rows.length&&ready[flushed]){
            const bytes=results[flushed];results[flushed]=undefined;
            done(rows[flushed],bytes,flushed);flushed++;
          }
        }catch(error){stop(error);}
      }
    };
    await Promise.all(Array.from({length:Math.min(LIMIT,rows.length)},worker));
    if(failed)throw failure;
    if(flushed!==rows.length)throw Error('A required patcher file is unavailable.');
  }
  const json=bytes=>JSON.parse(new TextDecoder().decode(bytes));
  async function run(manifest,sources,progress,bundle,payloadOffset,timing=()=>{}) {
    if(manifest.format!==2||!manifest.construction)throw Error('This page requires an audited format 2 recipe.');
    // Wall time per step. Timing lines hold step names and counts only.
    let clock=performance.now();
    const lap=(step,extra)=>{const now=performance.now();timing({step,ms:Math.round(now-clock),...extra});clock=now;};
    const lock=json(await get(new URL('pipeline-lock.json',base)));
    const runtimeLock=json(await get(new URL('vendor/runtime-lock.json',base)));
    if(lock.schema!==1||runtimeLock.schema!==1)throw Error('Unsupported runtime manifest.');
    progress('Loading the pinned conversion runtimes.',62);
    const cache=new Map();
    for(const row of runtimeLock.files){
      if(!safe(row.path)||!row.path.startsWith('web/patcher/vendor/'))throw Error('Unsafe runtime path.');
      if(row.path.includes('/licenses/'))continue;
      const url=new URL(row.path.slice('web/patcher/'.length),base).href;
      cache.set(url,await get(url,row));
    }
    lap('fetch runtimes');
    const originalFetch=self.fetch.bind(self),originalImport=self.importScripts.bind(self),blobs=[];
    function script(url){
      const absolute=new URL(url,base).href,bytes=cache.get(absolute);
      if(!bytes)throw Error('An unpinned runtime script was requested.');
      const blob=URL.createObjectURL(new Blob([bytes],{type:'text/javascript'}));blobs.push(blob);originalImport(blob);
    }
    self.importScripts=(...urls)=>urls.forEach(script);
    self.fetch=async(request,options)=>{
      const url=new URL(typeof request==='string'||request instanceof URL?String(request):request.url,base).href;
      if(!cache.has(url))throw Error('An unpinned runtime download was requested.');
      return new Response(cache.get(url),{status:200,headers:{'Content-Type':url.endsWith('.wasm')?'application/wasm':'application/octet-stream'}});
    };
    let py;
    try {
      script(new URL('vendor/pyodide/pyodide.js',base));
      py=await loadPyodide({indexURL:new URL('vendor/pyodide/',base).href});
      await py.loadPackage('pillow');
    } finally {
      self.fetch=originalFetch;self.importScripts=originalImport;
    }
    lap('start Pyodide and Pillow');
    const FS=py.FS;
    for(const directory of ['tools','src','assets/generated','assets/private','build/retail','cd','program','browser'])FS.mkdirTree('/project/'+directory);
    const put=(path,bytes)=>{
      if(!safe(path))throw Error('Unsafe conversion file path.');
      const target='/project/'+path;FS.mkdirTree(target.slice(0,target.lastIndexOf('/')));FS.writeFile(target,bytes);
    };
    progress('Checking the pinned conversion sources.',64);
    for(const row of lock.project)if(!safe(row.path))throw Error('Unsafe source path.');
    await pool(lock.project,(row,signal)=>get(new URL('../../'+row.path,base),row,signal),(row,bytes)=>put(row.path,bytes));
    lap('fetch project files',{files:lock.project.length});
    // These URLs contain only public source references and pinned release paths.
    // Disc names, hashes, BIOS data and user files are never sent.
    progress('Checking the pinned reference files.',66);
    for(const row of lock.references){
      const commitPinned=/^https:\/\/raw\.githubusercontent\.com\/[^/]+\/[^/]+\/[a-f0-9]{40}\//.test(row.url);
      const gccRelease=row.path==='.deps/gcc-13.4.0/libgcc/libgcc2.c'&&row.release==='releases/gcc-13.4.0'&&row.url==='https://raw.githubusercontent.com/gcc-mirror/gcc/releases/gcc-13.4.0/libgcc/libgcc2.c';
      if(!safe(row.path)||!(commitPinned||gccRelease))throw Error('Unpinned reference URL.');
    }
    const store=await openCache(),count={hits:0};
    await pool(lock.references,(row,signal)=>getReference(store,row,signal,count),(row,bytes,i)=>{
      put(row.path,bytes);
      if(i%32===0)progress(`Checking reference ${i+1} of ${lock.references.length}.`,66+2*i/lock.references.length);
    });
    lap('fetch reference files',{files:lock.references.length,cache_hits:count.hits,cache:store?'available':'unavailable',concurrency:LIMIT});
    const selected={jp:[],us:[],bios:[]};
    manifest.sources.forEach((row,index)=>selected[row.role].push(sources[index]));
    for(const role of ['jp','us','bios'])SonicPyFS.mountFiles(FS,'/discs/'+role,selected[role]);
    const alias=(role,name,target)=>{FS.symlink('/discs/'+role+'/'+name,target);};
    for(let i=0;i<manifest.sources.length;i++){
      const row=manifest.sources[i];
      if(row.role==='jp'&&/\.cue$/i.test(row.name))alias('jp',row.name,'/project/assets/private/sonic-cd-japan.cue');
      if(row.role==='us')alias('us',row.name,'/project/build/retail/'+row.name);
      if(row.role==='bios')alias('bios',row.name,'/project/assets/private/bios_CD_U.bin');
    }
    const literal=new Uint8Array(await bundle.slice(payloadOffset).arrayBuffer());
    if(await digest(literal)!==manifest.construction.payload_sha256)throw Error('Program literal checksum failed.');
    put('program/literals.bin',literal);
    put('program/construction.json',new TextEncoder().encode(JSON.stringify(manifest.construction)));
    const factories={},modules={},binaries={};
    for(const name of ['genesis','sonic','fmv','iso']){
      script(new URL('vendor/native/'+name+'.js',base));
      factories[name]=self[{genesis:'GenesisFactory',sonic:'SonicFactory',fmv:'FmvFactory',iso:'IsoFactory'}[name]];
      binaries[name]=cache.get(new URL('vendor/native/'+name+'.wasm',base).href);
      modules[name]=new WebAssembly.Module(binaries[name]);
    }
    script(new URL('vendor/ffmpeg/ffmpeg-core.js',base));factories.ffmpeg=self.createFFmpegCore;
    binaries.ffmpeg=cache.get(new URL('vendor/ffmpeg/ffmpeg-core.wasm',base).href);modules.ffmpeg=new WebAssembly.Module(binaries.ffmpeg);
    for(const name of ['native.js','pyfs.js','audio.js'])put('browser/'+name,await get(new URL(name,base),lock.bridge[name]));
    for(const name of ['genesis.js','genesis.wasm'])put('browser/'+name,cache.get(new URL('vendor/native/'+name,base).href));
    for(const name of ['ffmpeg-core.js','ffmpeg-core.wasm'])put('browser/'+name,cache.get(new URL('vendor/ffmpeg/'+name,base).href));
    const backend=SonicNativeBridge.create({FS,binaries,modules,factories,mount:SonicPyFS.mount,pastFade:SonicAudio.pastFade,commits:lock.commits});
    backend.resetGenesis();py.globals.set('_patcher_backend',backend);
    py.globals.set('_patcher_construction',JSON.stringify(manifest.construction));
    py.globals.set('_patcher_core_sha',await digest(binaries.genesis));
    const bootstrap=await get(new URL('py/bootstrap.py',base),lock.bootstrap);
    py.runPython(new TextDecoder().decode(bootstrap));
    py.runPython('initialize(_patcher_backend,json.loads(_patcher_construction),_patcher_core_sha)');
    lap('mount inputs and initialize converters');
    for(let i=0;i<lock.commands.length;i++){
      const command=lock.commands[i];
      const label=`Converting ${i+1} of ${lock.commands.length}: ${command.script.split('/').pop()}`;
      progress(label,68+18*i/lock.commands.length);
      py.globals.set('_patcher_script',command.script);py.globals.set('_patcher_arguments',JSON.stringify(command.args));
      py.globals.set('_patcher_progress',(detail,completed,total)=>{
        if(!Number.isInteger(completed)||!Number.isInteger(total)||total<1||completed<0||completed>total)throw Error('Invalid conversion progress.');
        progress(`${label}: ${Math.min(completed+1,total)}/${total} ${detail}`,68+18*(i+completed/total)/lock.commands.length);
      });
      py.runPython('convert(_patcher_script,json.loads(_patcher_arguments),_patcher_progress)');
      await new Promise(resolve=>setTimeout(resolve,0));
      lap(`convert ${i+1} ${command.script.split('/').pop()}`);
    }
    py.runPython('verify_cd(json.loads(_patcher_construction))');
    lap('verify_cd');
    const output=new Map();
    for(const row of manifest.derivations){
      if(!safe(row.name))throw Error('Unsafe derived output path.');
      const data=FS.readFile('/project/'+row.name);
      if(data.length!==row.bytes||await digest(data)!==row.sha256)throw Error('A converted output failed its checksum: '+row.name);
      output.set(row.name,new Blob([data]));
    }
    blobs.forEach(url=>URL.revokeObjectURL(url));
    lap('hash converted outputs',{files:manifest.derivations.length});
    return output;
  }
  return {run};
})();
