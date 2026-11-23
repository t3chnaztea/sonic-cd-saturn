'use strict';
importScripts('release.js', 'engine.js', 'audio.js', 'pyfs.js', 'native.js', 'pipeline.js');
let running=false;
onmessage = async event => {
  if(running)return;
  running=true;
  try {
    const progress=(message,value)=>postMessage({kind:'progress',message,value});
    // Step names and milliseconds only. The page prints them to its console.
    const timing=row=>postMessage({kind:'timing',row});
    let clock=performance.now();
    const lap=step=>{const now=performance.now();timing({step,ms:Math.round(now-clock)});clock=now;};
    const started=clock;
    progress('Loading the audited program recipe.',1);
    const options={credentials:'omit',redirect:'error',referrerPolicy:'no-referrer'};
    const configResponse=await fetch('recipe-lock.json',options);
    if(!configResponse.ok)throw Error('This site package has no audited recipe.');
    const config=await configResponse.json();
    if(config.status!=='PASS'||!/^[a-f0-9]{64}$/.test(config.sha256))throw Error('This site package has no audited recipe.');
    const response=await fetch('recipe.scsp',options);
    if(!response.ok)throw Error('The audited program recipe is unavailable.');
    const bundle=await response.blob();
    if(await SonicPatch.sha256(bundle)!==config.sha256)throw Error('The program recipe failed its checksum.');
    const inspected=await SonicPatch.inspect(bundle,SONIC_RELEASE);
    lap('load and check recipe');
    const result = await SonicPatch.apply(bundle, event.data.files, SONIC_RELEASE,progress,
      async(manifest,sources,report)=>{
        lap('verify original files');
        const output=await SonicPipeline.run(manifest,sources,report,bundle,inspected.payload,timing);
        clock=performance.now();return output;
      });
    lap('build and verify final BIN');
    timing({step:'total',ms:Math.round(performance.now()-started)});
    postMessage({kind: 'result', result});
  } catch (error) { postMessage({kind: 'error', message: error.message || 'The patch could not be completed.'}); }
};
