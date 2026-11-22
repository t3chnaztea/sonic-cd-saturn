'use strict';
// Private-input regression. Only the receipt is written, under a new build folder.
const fs = require('node:fs'), path = require('node:path'), crypto = require('node:crypto');
const assert = require('node:assert/strict');
const {pastFade} = require('../web/patcher/audio.js');
const root = path.resolve(__dirname, '..');
const out = process.argv[2];
if (!out || !path.resolve(out).startsWith(path.join(root, 'build') + path.sep)) throw Error('Choose a new output directory under build/.');
fs.mkdirSync(out, {recursive: false});
const cases = [['past', 'build/retail/past.raw', 'assets/generated/music1.raw'],
  ...[3,4,5,6,7,8].map(n => ['R'+n, `build/japanese-past/R${n}.raw`, `build/japanese-past/R${n}-cdda.raw`])];
const sha = b => crypto.createHash('sha256').update(b).digest('hex');
const results = [];
for (const [name, source, native] of cases) {
  const input = fs.readFileSync(path.join(root, source)), expected = fs.readFileSync(path.join(root, native));
  const start = performance.now(), actual = pastFade(input), wall = (performance.now() - start) / 1000;
  const exact = Buffer.from(actual).equals(expected);
  results.push({name, input_sha256:sha(input), native_sha256:sha(expected), output_sha256:sha(actual),
    bytes:actual.byteLength, identical:exact, wall_seconds:wall, process_peak_rss_bytes:process.resourceUsage().maxRSS*1024});
  fs.writeFileSync(path.join(out, 'results.json'), JSON.stringify(results, null, 2)+'\n');
  assert.ok(exact, name+' fade differs');
}
console.log('PASS: arithmetic Past fade; 7/7 tracks byte-identical; no residuals');
