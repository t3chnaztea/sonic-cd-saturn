'use strict';
// Real local-file test. Requires Playwright and the user's private patch inputs.
const assert = require('node:assert/strict');
const fs = require('node:fs'), path = require('node:path'), http = require('node:http');
const {createHash} = require('node:crypto');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root = path.resolve(__dirname, '..'), site = path.join(root, 'web/patcher');
const release = require('../web/patcher/release.js');
const [bundleArg, outArg] = process.argv.slice(2);
if (!bundleArg || !outArg) throw new Error('Usage: node tools/test-browser-patch-ui.cjs PRIVATE.scsp NEW_BUILD_OUTPUT_DIR');
const bundle = path.resolve(bundleArg), out = path.resolve(outArg);
if (!out.startsWith(path.join(root, 'build') + path.sep)) throw new Error('Test output must stay under build/');
fs.mkdirSync(out, {recursive: false});
const downloads = path.join(out, 'downloads'); fs.mkdirSync(downloads);
const cue = fs.realpathSync(path.join(root, 'assets/private/sonic-cd-japan.cue'));
const sources = [...fs.readFileSync(cue, 'utf8').matchAll(/FILE\s+"([^"]+)" BINARY/g)].map(m => path.join(path.dirname(cue), m[1]));
const allowed = new Set(['index.html','style.css','app.js','worker.js','engine.js','release.js']);
const requests = [], errors = [];
const server = http.createServer((req,res) => {
  if (req.method !== 'GET') {res.writeHead(405).end();return;}
  const name = req.url === '/' ? 'index.html' : req.url.slice(1);
  if (name === 'favicon.ico') {res.writeHead(204).end();return;}
  if (!allowed.has(name)) {res.writeHead(404).end();return;}
  res.setHeader('Content-Type',name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':'text/html');
  fs.createReadStream(path.join(site,name)).pipe(res);
});
async function fileSha(file) {
  const hash=createHash('sha256');
  for await (const chunk of fs.createReadStream(file)) hash.update(chunk);
  return hash.digest('hex');
}
async function main() {
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const url=`http://127.0.0.1:${server.address().port}/`;
  const browser=await chromium.launch({headless:true,channel:process.env.BROWSER_CHANNEL || 'chrome',downloadsPath:downloads});
  try {
    const context=await browser.newContext({acceptDownloads:true,viewport:{width:1280,height:1000}});
    const page=await context.newPage();
    page.on('request',r=>requests.push({url:r.url(),method:r.method()}));
    page.on('pageerror',e=>errors.push(e.message));
    await page.goto(url);
    assert.equal(await page.locator('#run').isDisabled(),true);
    assert.equal(await page.locator('h1').innerText(),'Sonic CD.\nMeet Saturn.');
    await page.screenshot({path:path.join(out,'desktop.png'),fullPage:true});
    const bad=path.join(out,'invalid.scsp'); fs.writeFileSync(bad,'not a patch bundle');
    await page.getByLabel('Private patch bundle',{exact:true}).setInputFiles(bad);
    await page.getByLabel('Original Japanese disc BIN files',{exact:true}).setInputFiles(sources);
    await page.locator('#run').click();
    await page.waitForFunction(()=>document.querySelector('#status').dataset.error==='true');
    assert.match(await page.locator('#status').innerText(),/not a Sonic/);
    assert.equal(await page.locator('#results').isHidden(),true);
    await page.locator('#bundle').setInputFiles(bundle);
    await page.locator('#run').click();
    await page.locator('#cancel').click();
    assert.match(await page.locator('#status').innerText(),/Cancelled/);
    assert.equal(await page.locator('#downloads a').count(),0);
    assert.equal(await page.locator('#originals').isEnabled(),true);
    await page.locator('#run').click();
    await page.waitForFunction(()=>!document.querySelector('#results').hidden || document.querySelector('#status').dataset.error==='true',null,{timeout:300000});
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
    await page.locator('#bundle').setInputFiles(bad);
    assert.equal(await page.locator('#results').isHidden(),true);
    assert.equal(await page.locator('#downloads a').count(),0);
    assert.equal(errors.length,0,JSON.stringify(errors));
    assert.equal(requests.every(r=>r.url.startsWith(url)&&r.method==='GET'),true,'Unexpected network request');
    const report={status:'passed',tested_utc:new Date().toISOString(),browser:browser.version(),
      checks:['invalid bundle rejected','cancel restores controls','actual worker patch','downloaded BIN SHA-256','downloaded CUE SHA-256','receipt','desktop layout','390px layout','stale links cleared','no upload requests','no page errors'],
      bin_sha256:release.binSha256,cue_sha256:release.cueSha256,source_files:receipt.sources.length,requests:requests.length,hardware_tested:false};
    fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(report,null,2)+'\n');
    console.log('PASS: actual browser patch; downloaded BIN/CUE match accepted V0.082; 11 UI contracts');
  } finally {await browser.close();}
}
main().catch(error=>{console.error(error);process.exitCode=1;}).finally(()=>server.close());
