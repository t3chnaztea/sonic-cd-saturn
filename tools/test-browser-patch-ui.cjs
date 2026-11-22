'use strict';
// Real local-file test. Requires Playwright and the user's private patch inputs.
const assert = require('node:assert/strict');
const fs = require('node:fs'), path = require('node:path'), http = require('node:http');
const {createHash} = require('node:crypto');
const {pathToFileURL}=require('node:url');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root = path.resolve(__dirname, '..');
const fileMode=process.env.PATCHER_FILE_MODE==='1';
const release = require('../web/patcher/release.js');
const [siteArg, outArg] = process.argv.slice(2);
if (!siteArg || !outArg) throw new Error('Usage: node tools/test-browser-patch-ui.cjs AUDITED_SITE_ROOT NEW_BUILD_OUTPUT_DIR');
const site=path.resolve(siteArg),out=path.resolve(outArg);
const config=JSON.parse(fs.readFileSync(path.join(site,'web/patcher/recipe-lock.json'),'utf8'));
assert.equal(config.status,'PASS');
const lock=JSON.parse(fs.readFileSync(path.join(site,'web/patcher/pipeline-lock.json'),'utf8'));
const references=new Map(lock.references.map(row=>[new URL(row.url).href,path.join(root,row.path)]));
if (!out.startsWith(path.join(root, 'build') + path.sep)) throw new Error('Test output must stay under build/');
fs.mkdirSync(out, {recursive: false});
const downloads = path.join(out, 'downloads'); fs.mkdirSync(downloads);
const cue = fs.realpathSync(path.join(root, 'assets/private/sonic-cd-japan.cue'));
const sources = [cue,...[...fs.readFileSync(cue, 'utf8').matchAll(/FILE\s+"([^"]+)" BINARY/g)].map(m => path.join(path.dirname(cue), m[1]))];
const american=['sonic.bin','sonic.cue'].map(name=>path.join(root,'build/retail',name));
const bios=path.join(root,'assets/private/bios_CD_U.bin');
const requests=[],errors=[],unexpected=[];
const server=http.createServer((req,res)=>{
 if(req.method!=='GET'){res.writeHead(405).end();return;}
 let pathname;try{pathname=decodeURIComponent(new URL(req.url,'http://localhost').pathname);}catch{res.writeHead(400).end();return;}
 if(pathname.endsWith('/favicon.ico')){res.writeHead(204).end();return;}
 if(pathname.endsWith('/'))pathname+='index.html';
 const file=path.resolve(site,'.'+pathname);
 if(!file.startsWith(site+path.sep)||!fs.existsSync(file)||!fs.statSync(file).isFile()||!fs.realpathSync(file).startsWith(site+path.sep)){res.writeHead(404).end();return;}
 const type={'.js':'text/javascript','.mjs':'text/javascript','.wasm':'application/wasm','.json':'application/json','.css':'text/css','.html':'text/html'}[path.extname(file)]||'application/octet-stream';
 res.setHeader('Content-Type',type);fs.createReadStream(file).pipe(res);
});
async function fileSha(file) {
  const hash=createHash('sha256');
  for await (const chunk of fs.createReadStream(file)) hash.update(chunk);
  return hash.digest('hex');
}
async function main() {
  if(!fileMode)await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(0,'127.0.0.1',resolve);});
  const origin=fileMode?pathToFileURL(site).href:`http://127.0.0.1:${server.address().port}`,url=origin+'/web/patcher/';
  const args=['--disable-background-networking','--disable-component-update','--disable-sync','--no-first-run','--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1'];
  if(fileMode)args.push('--allow-file-access-from-files');
  const browser=await chromium.launch({headless:true,channel:process.env.BROWSER_CHANNEL || 'chrome',downloadsPath:downloads,args});
  const cancelWatch=require('./patcher_watch.cjs')(root,cause=>{errors.push(cause);void browser.close();});
  const terminate=()=>{browser.close().finally(()=>{server.close();process.exit(143);});};
  process.once('SIGTERM',terminate);
  try {
    const context=await browser.newContext({acceptDownloads:true,viewport:{width:1280,height:1000}});
    await context.route('**/*',async route=>{
      const r=route.request();if(r.method()!=='GET'||r.postData()){unexpected.push('upload');return route.abort();}
      if(r.url().startsWith(origin+'/'))return route.continue();
      if(r.url().startsWith('blob:'))return route.continue();
      const file=references.get(r.url());
      if(file)return route.fulfill({status:200,headers:{'access-control-allow-origin':'*','content-type':'application/octet-stream'},body:fs.readFileSync(file)});
      unexpected.push('unapproved request');return route.abort();
    });
    const page=await context.newPage();
    page.on('request',r=>requests.push({url:r.url(),method:r.method(),has_body:!!r.postData()}));
    page.on('pageerror',e=>errors.push(e.message));
    await page.goto(url);
    assert.equal(await page.locator('#run').isDisabled(),true);
    assert.equal(await page.locator('h1').innerText(),'Sonic CD.\nMeet Saturn.');
    await page.screenshot({path:path.join(out,'desktop.png'),fullPage:true});
    assert.match(await page.title(),/Easy Patcher/);assert.equal(await page.locator('#bundle').count(),0);
    const bad=path.join(out,'bad-bios.bin');fs.writeFileSync(bad,'invalid BIOS');
    await page.locator('#japanese').setInputFiles(sources);
    await page.locator('#american').setInputFiles(american);
    await page.locator('#bios').setInputFiles(bad);
    await page.locator('#run').click();
    await page.waitForFunction(()=>document.querySelector('#status').dataset.error==='true');
    assert.match(await page.locator('#status').innerText(),/size|checksum|Missing/i);
    assert.equal(await page.locator('#results').isHidden(),true);
    await page.locator('#bios').setInputFiles(bios);
    await page.locator('#run').click();
    await page.locator('#cancel').click();
    assert.match(await page.locator('#status').innerText(),/Cancelled/);
    assert.equal(await page.locator('#downloads a').count(),0);
    assert.equal(await page.locator('#bios').isEnabled(),true);
    await page.locator('#run').click();
    let last='';
    const heartbeat=setInterval(async()=>{try{
      const text=await page.locator('#status').innerText();
      if(text!==last){last=text;fs.appendFileSync(path.join(out,'progress.log'),text+'\n');}
    }catch{}},5000);
    try {await page.waitForFunction(()=>!document.querySelector('#results').hidden || document.querySelector('#status').dataset.error==='true',null,{timeout:7200000});}
    finally {clearInterval(heartbeat);}
    assert.equal(await page.locator('#status').getAttribute('data-error'),'false',await page.locator('#status').innerText());
    assert.equal(await page.locator('#downloads a').count(),3);
    assert.equal(await page.locator('#progress').evaluate(element=>element.value),100);
    for (const link of await page.locator('#downloads a').all()) {
      const pending=page.waitForEvent('download'); await link.click(); const download=await pending;
      assert.equal(await download.failure(),null);
      const destination=path.join(downloads,download.suggestedFilename());
      assert.equal(fs.existsSync(destination),false);
      fs.renameSync(await download.path(),destination);
    }
    assert.equal(await fileSha(path.join(downloads,release.binName)),release.binSha256);
    assert.equal(await fileSha(path.join(downloads,release.cueName)),release.cueSha256);
    const receipt=JSON.parse(fs.readFileSync(path.join(downloads,'sonic-cd-saturn-v0082-receipt.json'),'utf8'));
    assert.equal(receipt.hardware_tested,false);
    assert.equal(receipt.bin.bytes,release.binBytes);
    await page.screenshot({path:path.join(out,'verified-desktop.png'),fullPage:true});
    await page.setViewportSize({width:390,height:844});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    await page.screenshot({path:path.join(out,'mobile.png'),fullPage:true});
    // An edited input invalidates all old downloads.
    await page.locator('#bios').setInputFiles(bad);
    assert.equal(await page.locator('#results').isHidden(),true);
    assert.equal(await page.locator('#downloads a').count(),0);
    assert.equal(errors.length,0,JSON.stringify(errors));
    assert.deepEqual(unexpected,[]);
    assert.equal(requests.every(r=>(r.url.startsWith(origin+'/')||r.url.startsWith('blob:')||references.has(r.url))&&r.method==='GET'&&!r.has_body),true,'Unexpected network request');
    const report={status:'passed',tested_utc:new Date().toISOString(),browser:browser.version(),
      checks:['bad BIOS rejected','cancel restores controls','actual worker patch','downloaded BIN SHA-256','downloaded CUE SHA-256','receipt','desktop layout','390px layout','stale links cleared','no upload requests','no page errors'],
      bin_sha256:release.binSha256,cue_sha256:release.cueSha256,source_files:receipt.sources.length,requests:requests.length,transport:fileMode?'offline-file':'loopback-http',live_reference_fetch_tested:false,hardware_tested:false};
    fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(report,null,2)+'\n');
    console.log('PASS: actual Chrome Easy Patcher; downloaded BIN/CUE match accepted V0.082; no uploads'+(fileMode?'; offline file mode':''));
  } finally {cancelWatch();process.removeListener('SIGTERM',terminate);await browser.close();}
}
main().catch(error=>{console.error(error);console.log('FAIL: actual Chrome Easy Patcher');process.exitCode=1;}).finally(()=>{if(server.listening)server.close();});
