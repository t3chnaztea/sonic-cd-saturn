'use strict';
// One real Chrome conversion. No repeated game QA or BIOS campaigns.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),http=require('node:http');
const {createHash}=require('node:crypto');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const root=path.resolve(__dirname,'..'),release=require('../web/patcher/release.js');
const [siteArg,outArg]=process.argv.slice(2);
if(!siteArg||!outArg)throw Error('Usage: test-background-progress-ui.cjs AUDITED_SITE NEW_BUILD_DIR');
const site=path.resolve(siteArg),out=path.resolve(outArg);
assert(out.startsWith(path.join(root,'build')+path.sep));
fs.mkdirSync(out);const downloads=path.join(out,'downloads');fs.mkdirSync(downloads);
const lock=JSON.parse(fs.readFileSync(path.join(site,'web/patcher/pipeline-lock.json')));
const refs=new Map(lock.references.map(row=>[row.url,path.join(root,row.path)]));
const cue=fs.realpathSync(path.join(root,'assets/private/sonic-cd-japan.cue'));
const jp=[cue,...[...fs.readFileSync(cue,'utf8').matchAll(/FILE\s+"([^"]+)" BINARY/g)].map(m=>path.join(path.dirname(cue),m[1]))];
const us=['sonic.bin','sonic.cue'].map(n=>path.join(root,'build/retail',n));
const bios=path.join(root,'assets/private/bios_CD_U.bin');
const rows=[],errors=[],badRequests=[];
const server=http.createServer((req,res)=>{
  if(req.method!=='GET'){res.writeHead(405).end();return;}
  const url=new URL(req.url,'http://localhost');
  if(url.pathname.endsWith('/favicon.ico')){res.writeHead(204).end();return;}
  const file=path.resolve(site,'.'+decodeURIComponent(url.pathname)+(url.pathname.endsWith('/')?'index.html':''));
  if(!file.startsWith(site+path.sep)||!fs.existsSync(file)||!fs.statSync(file).isFile()||!fs.realpathSync(file).startsWith(site+path.sep)){res.writeHead(404).end();return;}
  res.setHeader('Content-Type',({'.js':'text/javascript','.json':'application/json','.wasm':'application/wasm','.css':'text/css','.html':'text/html'})[path.extname(file)]||'application/octet-stream');
  fs.createReadStream(file).pipe(res);
});
async function sha(file){const h=createHash('sha256');for await(const chunk of fs.createReadStream(file))h.update(chunk);return h.digest('hex');}
async function main(){
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const origin=`http://127.0.0.1:${server.address().port}`;
  const browser=await chromium.launch({headless:true,channel:'chrome',downloadsPath:downloads,args:['--disable-background-networking','--disable-component-update','--disable-sync','--no-first-run','--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1']});
  const cancelWatch=require('./patcher_watch.cjs')(root,cause=>{errors.push(cause);void browser.close();});
  const terminate=()=>{browser.close().finally(()=>{server.close();process.exit(143);});};process.once('SIGTERM',terminate);
  try{
    const context=await browser.newContext({acceptDownloads:true,viewport:{width:1280,height:1000}});
    await context.route('**/*',async route=>{
      const request=route.request(),url=request.url();
      if(request.method()!=='GET'||request.postData()){badRequests.push('upload');return route.abort();}
      if(url.startsWith(origin+'/')||url.startsWith('blob:'))return route.continue();
      if(refs.has(url))return route.fulfill({status:200,headers:{'access-control-allow-origin':'*'},body:fs.readFileSync(refs.get(url))});
      badRequests.push(url);return route.abort();
    });
    const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
    await page.exposeFunction('recordConversionProgress',row=>{rows.push(row);fs.appendFileSync(path.join(out,'progress.jsonl'),JSON.stringify(row)+'\n');});
    await page.goto(origin+'/web/patcher/');
    await page.evaluate(()=>{
      window.backgroundSubsteps=[];
      const status=document.querySelector('#status');
      new MutationObserver(()=>{
        const text=status.textContent,background=/^Converting 23 of \d+: background_tables\.py: /.test(text);
        const row={text,value:document.querySelector('#progress').value,resultsHidden:document.querySelector('#results').hidden,at:performance.now()};
        if(background)window.backgroundSubsteps.push(row);
        window.recordConversionProgress(row);
      }).observe(status,{childList:true,characterData:true,subtree:true});
    });
    await page.locator('#japanese').setInputFiles(jp);await page.locator('#american').setInputFiles(us);await page.locator('#bios').setInputFiles(bios);
    await page.locator('#run').click();
    await page.waitForFunction(()=>window.backgroundSubsteps.length>=2||document.querySelector('#status').dataset.error==='true',null,{timeout:3600000});
    assert.equal(await page.locator('#status').getAttribute('data-error'),'false',await page.locator('#status').innerText());
    assert.equal(await page.locator('#results').isHidden(),true);
    await page.screenshot({path:path.join(out,'step23-running.png'),fullPage:true});
    await page.waitForFunction(()=>!document.querySelector('#results').hidden||document.querySelector('#status').dataset.error==='true',null,{timeout:7200000});
    assert.equal(await page.locator('#status').getAttribute('data-error'),'false',await page.locator('#status').innerText());
    const substeps=await page.evaluate(()=>window.backgroundSubsteps);
    assert.equal(new Set(substeps.map(row=>row.text)).size,17);
    assert.equal(new Set(substeps.map(row=>row.text.match(/: (\d+)\/16 /)?.[1])).size,16);
    assert(substeps.every(row=>row.resultsHidden));
    assert(substeps.every((row,i)=>i===0||row.value>=substeps[i-1].value));
    assert(substeps.some(row=>row.text.endsWith('Background tables ready')));
    const links=page.locator('#downloads a');assert.equal(await links.count(),3);
    for(const link of await links.all()){
      const pending=page.waitForEvent('download');await link.click();const download=await pending;
      assert.equal(await download.failure(),null);const target=path.join(downloads,download.suggestedFilename());assert(!fs.existsSync(target));fs.renameSync(await download.path(),target);
    }
    assert.equal(await sha(path.join(downloads,release.binName)),release.binSha256);
    assert.equal(await sha(path.join(downloads,release.cueName)),release.cueSha256);
    assert.deepEqual(errors,[]);assert.deepEqual(badRequests,[]);
    await page.screenshot({path:path.join(out,'verified.png'),fullPage:true});
    const report={status:'PASS',browser:browser.version(),checked_utc:new Date().toISOString(),substeps,bin_sha256:release.binSha256,cue_sha256:release.cueSha256,errors,badRequests,live_reference_fetch_tested:false};
    fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(report,null,2)+'\n');
    console.log('PASS: Chrome step23 progress; 16 substeps visible before completion; exact V0.082 BIN/CUE; no uploads');
  }finally{cancelWatch();process.removeListener('SIGTERM',terminate);await browser.close();}
}
main().catch(error=>{console.error(error);process.exitCode=1;}).finally(()=>server.close());
