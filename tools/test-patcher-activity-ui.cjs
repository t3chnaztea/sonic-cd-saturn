'use strict';
// Fast presentation test. Worker messages are simulated; no game conversion runs.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),http=require('node:http');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const root=path.resolve(__dirname,'..'),site=path.join(root,'web/patcher'),out=path.resolve(process.argv[2]||'build/patcher-activity-ui');
assert(out.startsWith(path.join(root,'build')+path.sep));fs.mkdirSync(out);
const files=new Set(['index.html','style.css','release.js','app.js']);
const server=http.createServer((req,res)=>{
 const name=req.url==='/'?'index.html':req.url.slice(1);
 if(name==='favicon.ico'){res.writeHead(204).end();return;}
 if(req.method!=='GET'||!files.has(name)){res.writeHead(404).end();return;}
 res.setHeader('Content-Type',name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':'text/html');fs.createReadStream(path.join(site,name)).pipe(res);
});
async function main(){
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const browser=await chromium.launch({headless:true,channel:'chrome'}),errors=[],uploads=[];
 try{
  const page=await browser.newPage({viewport:{width:1280,height:1000}});page.on('pageerror',e=>errors.push(e.message));
  page.on('request',r=>{if(r.method()!=='GET'||r.postData())uploads.push(r.url());});
  await page.clock.install({time:new Date('2026-11-23T04:00:00Z')});
  await page.addInitScript(()=>{window.workers=[];window.Worker=class{
   constructor(){this.terminated=false;window.workers.push(this);window.currentWorker=this;}
   postMessage(data){this.input=data;}
   terminate(){this.terminated=true;}
   emit(data){this.onmessage?.({data});}
  };});
  await page.goto(process.env.PATCHER_ACTIVITY_URL||`http://127.0.0.1:${server.address().port}/`);
  assert.match(await page.locator('.duration-note').innerText(),/17 minutes.*M4 Mac/);
  assert.equal(await page.locator('#activity').isHidden(),true);
  for(const id of ['japanese','american','bios'])await page.locator('#'+id).setInputFiles({name:id+'.bin',mimeType:'application/octet-stream',buffer:Buffer.from('UI fixture')});
  const emit=data=>page.evaluate(data=>window.currentWorker.emit(data),data);
  await page.locator('#run').click();
  await emit({kind:'progress',message:'Converting 23 of 56: background_tables.py',value:75});
  assert.equal(await page.locator('#step23-remaining').innerText(),'~17:00');
  await page.clock.fastForward(65000);
  assert.equal(await page.locator('#elapsed').innerText(),'01:05');
  assert.equal(await page.locator('#step23-remaining').innerText(),'~15:55');
  assert.equal(await page.locator('#last-update').innerText(),'01:05 ago');
  assert.equal(await page.locator('#progress').evaluate(e=>e.value),75,'Timer must not fabricate conversion progress');
  await emit({kind:'progress',message:'Converting 23 of 56: background_tables.py: 2/16 Extracting Collision Chaos scroll rules',value:75.02});
  assert.equal(await page.locator('#step23-remaining').innerText(),'~15:55','Substeps must not reset countdown');
  await page.screenshot({path:path.join(out,'desktop.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  await page.clock.resume();
  await page.locator('#activity').screenshot({path:path.join(out,'mobile.png')});
  await page.setViewportSize({width:1280,height:1000});
  await page.clock.fastForward(17*60000);
  assert.equal(await page.locator('#step23-remaining').innerText(),'Estimate exceeded');
  assert.equal(await page.locator('#activity-state').innerText(),'Running');
  assert.equal(await page.evaluate(()=>window.currentWorker.terminated),false,'Estimate must not cancel worker');
  // Replay the real substep messages if the recorded local trace is supplied.
  const trace=process.env.PATCHER_PROGRESS_TRACE;
  if(trace){
   const rows=fs.readFileSync(trace,'utf8').trim().split('\n').map(JSON.parse).filter(r=>/^Converting 23 of \d+: background_tables\.py: /.test(r.text));
   assert.equal(rows.length,17);
   for(const row of rows)await emit({kind:'progress',message:row.text,value:row.value});
   assert.match(await page.locator('#activity-log').innerText(),/16\/16 Background tables ready/);
  }
  await emit({kind:'progress',message:'Converting 24 of 56: inventory_objects.py',value:75.4});
  assert.equal(await page.locator('#step23-clock').isHidden(),true);
  await emit({kind:'error',message:'Test failure <img src=x onerror=alert(1)>'});
  assert.equal(await page.locator('#activity-state').innerText(),'Error');
  assert.equal(await page.locator('#activity-log img').count(),0);
  const frozen=await page.locator('#elapsed').innerText();await page.clock.fastForward(60000);
  assert.equal(await page.locator('#elapsed').innerText(),frozen);
  await page.locator('#run').click();
  assert.equal(await page.locator('#elapsed').innerText(),'00:00');
  assert.equal(await page.locator('#activity-log li').count(),1);
  await page.evaluate(()=>window.workers[0].emit({kind:'progress',message:'stale worker',value:99}));
  assert.doesNotMatch(await page.locator('#status').innerText(),/stale/);
  await emit({kind:'progress',message:'Converting 23 of 56: background_tables.py',value:75});
  await page.clock.fastForward(1000);await page.locator('#cancel').click();
  assert.equal(await page.locator('#activity-state').innerText(),'Cancelled');
  assert.match(await page.locator('#activity-log').innerText(),/Cancelled/);
  const cancelled=await page.locator('#elapsed').innerText();await page.clock.fastForward(60000);
  assert.equal(await page.locator('#elapsed').innerText(),cancelled);
  await page.locator('#run').click();
  await page.evaluate(()=>{for(let i=0;i<300;i++)window.currentWorker.emit({kind:'progress',message:'Test update '+i,value:75});});
  assert.equal(await page.locator('#activity-log li').count(),250);
  await page.evaluate(()=>window.currentWorker.emit({kind:'result',result:{bin:new Blob(['synthetic']),cue:new Blob(['synthetic']),receipt:{test:true}}}));
  assert.equal(await page.locator('#activity-state').innerText(),'Complete');assert.equal(await page.locator('#downloads a').count(),3);
  await page.locator('#bios').setInputFiles({name:'new.bin',mimeType:'application/octet-stream',buffer:Buffer.from('UI fixture')});
  assert.equal(await page.locator('#activity').isHidden(),true);assert.equal(await page.locator('#activity-log li').count(),0);assert.equal(await page.locator('#downloads a').count(),0);
  assert.deepEqual(errors,[]);
  assert.deepEqual(uploads,[]);
  fs.writeFileSync(path.join(out,'report.json'),JSON.stringify({status:'PASS',mode:'UI simulation, no game conversion',live:!!process.env.PATCHER_ACTIVITY_URL,browser:browser.version(),checks:['M4 runtime note','elapsed clock without worker messages','estimated countdown','substeps retain countdown','overrun does not cancel','real substep trace replay','running log','error freezes clocks','safe log text','new run resets','stale worker ignored','cancel freezes clocks','bounded log','completion','input reset','390px layout','no page errors','no uploads']},null,2)+'\n');
  console.log('PASS: Chrome activity UI; runtime note, countdown, elapsed clock, log, cancel/error/reset; no game conversion');
 }finally{await browser.close();}
}
main().catch(error=>{console.error(error);process.exitCode=1;}).finally(()=>server.close());
