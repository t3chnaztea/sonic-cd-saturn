'use strict';
// All factories and modules are compiled and hash-checked before Python starts.
// instantiateWasm keeps fresh emulator creation synchronous inside a Python call.
const SonicNativeBridge = (() => {
  function create({FS, modules, binaries, factories, mount, pastFade, commits}) {
    let core, ffmpeg, initialized=false;
    const callbackPointers=[];
    const array = value => value?.toJs ? value.toJs() : value;
    const bytes = value => {
      const data=array(value);
      if(!(data instanceof Uint8Array)) throw Error('Native bridge expected byte data.');
      return data;
    };
    function fresh(name, extra={}) {
      let ready;
      const options={...extra,noInitialRun:true,wasmBinary:binaries[name],
        onRuntimeInitialized(){ready=this;}};
      // Emscripten 4's instantiateWasm hook always returns a Promise, even
      // with synchronous compilation selected. Use its local binary path.
      // The separately pinned ffmpeg 3.x loader supports the synchronous hook.
      if(name==='ffmpeg')options.instantiateWasm=function(imports,receive) {
          const instance=new WebAssembly.Instance(modules[name],imports);
          receive(instance,modules[name]);return instance.exports;
      };
      const promise=factories[name](options);
      if(promise.catch)promise.catch(error=>{throw error;});
      if(!ready) throw Error(`Native module did not initialize synchronously: ${name}`);
      mount(ready,FS);
      // Path.resolve() follows the workspace aliases into the read-only disc mounts.
      if(FS.analyzePath('/discs').exists)mount(ready,FS,'/discs');
      return ready;
    }
    function current() { if(!core) throw Error('Genesis module is not initialized.');return core; }
    function call(name,args) {
      if(name==='retro_init'){name='patcher_init';initialized=true;}
      if(name==='retro_deinit')initialized=false;
      const m=current(),fn=m['_'+name];
      if(typeof fn!=='function')throw Error(`Unsupported Genesis function: ${name}`);
      return fn(...array(args));
    }
    function resetGenesis() {
      if(core && initialized)core._retro_deinit();
      for(const entry of callbackPointers){core.removeFunction(entry.pointer);entry.callback.destroy();}
      core=fresh('genesis',{print:()=>{},printErr:()=>{}});
      initialized=false;
      callbackPointers.length=0;
    }
    function callback(name,fn) {
      if(name==='retro_set_environment')return; // Fixed system directory/options in the C adapter.
      const signatures={retro_set_video_refresh:'viiii',retro_set_audio_sample_batch:'iii',
        retro_set_audio_sample:'vii',retro_set_input_poll:'v',retro_set_input_state:'iiiii'};
      if(!signatures[name])throw Error('Unsupported emulator callback.');
      const m=current(),retained=fn.copy(),pointer=m.addFunction((...args)=>retained(...args),signatures[name]);
      callbackPointers.push({pointer,callback:retained});m['_'+name](pointer);
    }
    function loadGame(path) {
      const m=current(),text=new TextEncoder().encode(path+'\0'),p=m._malloc(text.length),game=m._malloc(16);
      try {
        m.HEAPU8.set(text,p);
        const view=new DataView(m.HEAPU8.buffer);
        for(let i=0;i<4;i++)view.setUint32(game+i*4,i===0?p:0,true);
        return m._retro_load_game(game);
      } finally {m._free(game);m._free(p);}
    }
    function symbol(name) { return current().ccall('patcher_symbol','number',['string'],[name]); }
    function readMemory(address,length) {
      const heap=current().HEAPU8;
      if(!Number.isSafeInteger(address)||!Number.isSafeInteger(length)||address<0||length<0||address+length>heap.length)throw Error('Emulator memory read exceeds its bounds.');
      return heap.slice(address,address+length);
    }
    function writeMemory(address,data) {
      const view=data.getBuffer('u8');
      try {
        const raw=view.data.subarray(view.offset,view.offset+view.shape[0]),heap=current().HEAPU8;
        if(view.shape.length!==1||!Number.isSafeInteger(address)||address<0||address+raw.length>heap.length)throw Error('Emulator memory write exceeds its bounds.');
        heap.set(raw,address);
      } finally {view.release();}
    }
    function readMemoryInto(address,destination) {
      const view=destination.getBuffer('u8');
      try {
        const length=view.shape[0],heap=current().HEAPU8;
        if(view.readonly||view.shape.length!==1||!Number.isSafeInteger(address)||address<0||address+length>heap.length)throw Error('Emulator memory read exceeds its bounds.');
        view.data.set(heap.subarray(address,address+length),view.offset);
      } finally {view.release();}
    }
    function decodeSonic(source) {
      const m=fresh('sonic');
      const view=source.getBuffer('u8');
      try {m.FS.writeFile('/input',view.data.subarray(view.offset,view.offset+view.shape[0]));}
      finally {view.release();}
      if(m.callMain(['/input','/output'])!==0)throw Error('Sonic pose decoding failed.');
      return m.FS.readFile('/output');
    }
    function decodeSonicInto(source,destination) {
      const data=decodeSonic(source),view=destination.getBuffer('u8');
      try {
        if(view.readonly||view.shape.length!==1||view.shape[0]!==data.length)throw Error('Unexpected Sonic decoder output size.');
        view.data.set(data,view.offset);
      } finally {view.release();}
    }
    function runTool(request,cwd) {
      const args=array(request).map(String),tool=args[0].split('/').pop();
      if(cwd!=='/project')throw Error('Native tool outside conversion workspace.');
      if(tool==='git' && args.length===5 && args[1]==='-C' && args[3]==='rev-parse' && args[4]==='HEAD') {
        const dependency=args[2].split('/').pop();
        if(!commits[dependency])throw Error('Unknown pinned source.');
        return {code:0,stdout:commits[dependency]+'\n',stderr:''};
      }
      if(tool==='make' && args[1]==='-C' && args[2].endsWith('/.deps/genesis-plus-gx')) {
        if(!modules.genesis)throw Error('Pinned Genesis WASM module missing.');
        return {code:0,stdout:'Using verified Genesis WASM module.\n',stderr:''};
      }
      if(tool==='ffmpeg') {
        const input=args[args.indexOf('-i')+1],output=args[args.length-1],filter=args[args.indexOf('-af')+1];
        if(!input.startsWith('/project/build/')||!['/project/build/','/project/assets/generated/'].some(p=>output.startsWith(p)))throw Error('Audio path outside conversion workspace.');
        if(filter.startsWith('volume=1.5,afade=t=out:st=') && filter.endsWith(':d=3')) {
          FS.writeFile(output,pastFade(FS.readFile(input)));
          return {code:0,stdout:'',stderr:''};
        }
        if(filter!=='volume=1.7')throw Error('Unreviewed audio filter chain.');
        if(!ffmpeg)ffmpeg=fresh('ffmpeg');
        const log=[];ffmpeg.setLogger(({message})=>log.push(message));ffmpeg.reset();
        const code=ffmpeg.exec(...args.slice(1));
        return {code,stdout:'',stderr:log.join('\n')};
      }
      if(tool==='iso_to_raw') {
        const log=[],m=fresh('iso',{print:s=>log.push(s),printErr:s=>log.push(s)});
        const code=m.callMain(args.slice(1));return {code,stdout:log.join('\n'),stderr:''};
      }
      throw Error(`Native tool is not available in the browser: ${tool}`);
    }
    return {resetGenesis,callback,loadGame,symbol,readMemory,readMemoryInto,writeMemory,decodeSonic,decodeSonicInto,runTool,call};
  }
  return {create};
})();
if(typeof module!=='undefined')module.exports=SonicNativeBridge;
