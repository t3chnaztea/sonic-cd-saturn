'use strict';
// Small synthetic fixtures exercise the parser without any game data.
const assert = require('node:assert/strict');
const {createHash} = require('node:crypto');
const engine = require('../web/patcher/engine.js');
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const source = new File(['original audio'], 'track.bin');
const cue = 'FILE "test.bin" BINARY\n';
const expected = Buffer.from('original audio plus native code');
const release = {version:'V0.082',binName:'test.bin',cueName:'test.cue',binBytes:expected.length,binSha256:sha(expected),cueSha256:sha(cue)};
const header = {format:1,version:'V0.082',sources:[{name:'track.bin',bytes:source.size,sha256:sha('original audio')}],target:{bytes:expected.length,sha256:sha(expected),cue,cue_sha256:sha(cue)},ops:[{kind:'source',index:0,offset:0,length:source.size},{kind:'literal',offset:0,length:17}]};
function bundle(data=header, payload=' plus native code') {
  const text=Buffer.from(JSON.stringify(data)), prefix=Buffer.alloc(12);
  prefix.write('SCSP082\n'); prefix.writeUInt32LE(text.length,8);
  return new Blob([prefix,text,payload]);
}
async function main() {
  const result=await engine.apply(bundle(),[source],release);
  assert.equal(Buffer.from(await result.bin.arrayBuffer()).toString(),expected.toString());
  assert.equal(await result.cue.text(),cue);
  assert.equal(result.receipt.hardware_tested,false);
  await assert.rejects(engine.apply(bundle(),[],release),/Missing original/);
  await assert.rejects(engine.apply(bundle(),[source,source],release),/same name/);
  await assert.rejects(engine.apply(bundle(),[new File(['wrong'],source.name)],release),/Wrong size/);
  await assert.rejects(engine.apply(bundle(),[new File(['changed bytes!'],source.name)],release),/Checksum failed/);
  await assert.rejects(engine.apply(bundle(header,' plus broken code'),[source],release),/Output checksum/);
  await assert.rejects(engine.inspect(new Blob(['not a bundle at all']),release),/not a Sonic/);
  const bad=structuredClone(header);bad.ops[0].offset=Number.MAX_SAFE_INTEGER;
  await assert.rejects(engine.inspect(bundle(bad),release),/range exceeds/);
  const negative=structuredClone(header);negative.ops[0].offset=-1;
  await assert.rejects(engine.inspect(bundle(negative),release),/invalid range/);
  const other=structuredClone(header);other.target.sha256='0'.repeat(64);
  await assert.rejects(engine.inspect(bundle(other),release),/accepted V0.082/);
  const truncated=structuredClone(header);truncated.ops.pop();
  await assert.rejects(engine.inspect(bundle(truncated),release),/incomplete/);
  const escape=structuredClone(header);escape.sources[0].name='../track.bin';
  await assert.rejects(engine.inspect(bundle(escape),release),/invalid or repeated/);
  const cueBad=structuredClone(header);cueBad.target.cue+='REM broken\n';
  await assert.rejects(engine.inspect(bundle(cueBad),release),/CUE checksum/);
  console.log('PASS: browser patch engine; exact copy/literal output and 12 rejection contracts');
}
main().catch(error=>{console.error(error);process.exitCode=1;});
