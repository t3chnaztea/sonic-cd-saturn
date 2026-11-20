'use strict';
// A deliberately small copy/literal format. All reads are from selected local Files.
const SonicPatch = (() => {
  const MAGIC = 'SCSP082\n';
  const fail = message => { throw new Error(message); };
  const integer = n => Number.isSafeInteger(n) && n >= 0;
  const hash = s => typeof s === 'string' && /^[a-f0-9]{64}$/.test(s);
  const name = s => typeof s === 'string' && s.length > 0 && s.length < 256 && !/[\\/\x00-\x1f]/.test(s);
  async function sha256(blob) {
    const digest = await crypto.subtle.digest('SHA-256', await blob.arrayBuffer());
    return Array.from(new Uint8Array(digest), x => x.toString(16).padStart(2, '0')).join('');
  }
  async function inspect(bundle, release) {
    if (!bundle || bundle.size < 12) fail('Choose a complete .scsp patch bundle.');
    const prefix = new Uint8Array(await bundle.slice(0, 12).arrayBuffer());
    if (new TextDecoder().decode(prefix.slice(0, 8)) !== MAGIC) fail('This is not a Sonic CD Saturn patch bundle.');
    const length = new DataView(prefix.buffer).getUint32(8, true);
    if (!length || length > 16 * 1024 * 1024 || length + 12 > bundle.size) fail('The patch header is truncated or too large.');
    let data;
    try { data = JSON.parse(await bundle.slice(12, length + 12).text()); }
    catch { fail('The patch header is damaged.'); }
    if (data?.format !== 1 || data.version !== release.version || !Array.isArray(data.sources) || !data.sources.length || data.sources.length > 64 || !Array.isArray(data.ops) || !data.ops.length || data.ops.length > 400000) fail('The patch format or release is unsupported.');
    const target = data.target;
    if (!target || target.bytes !== release.binBytes || target.sha256 !== release.binSha256 || target.cue_sha256 !== release.cueSha256 || typeof target.cue !== 'string' || target.cue.length > 16384) fail('This bundle does not produce the accepted V0.082 release.');
    if (await sha256(new Blob([target.cue])) !== release.cueSha256) fail('The output CUE checksum failed.');
    const names = new Set();
    for (const source of data.sources) {
      if (!source || !name(source.name) || names.has(source.name) || !integer(source.bytes) || !source.bytes || source.bytes > 2 ** 31 || !hash(source.sha256)) fail('The patch has an invalid or repeated source file.');
      names.add(source.name);
    }
    const payload = 12 + length;
    let total = 0;
    for (const op of data.ops) {
      if (!op || !integer(op.offset) || !integer(op.length) || !op.length) fail('The patch has an invalid range.');
      let limit;
      if (op.kind === 'source') {
        if (!integer(op.index) || op.index >= data.sources.length) fail('The patch refers to a missing source.');
        limit = data.sources[op.index].bytes;
      } else if (op.kind === 'literal') limit = bundle.size - payload;
      else fail('The patch has an unsupported operation.');
      if (!integer(op.offset + op.length) || op.offset + op.length > limit) fail('The patch range exceeds its file.');
      total += op.length;
      if (!integer(total) || total > release.binBytes) fail('The patch output is too large.');
    }
    if (total !== release.binBytes) fail('The patch output is incomplete.');
    return {data, payload};
  }
  async function apply(bundle, files, release, progress = () => {}) {
    progress('Reading the patch bundle.', 1);
    const {data, payload} = await inspect(bundle, release);
    const byName = new Map();
    for (const file of files) {
      if (byName.has(file.name)) fail('Two selected files have the same name. Choose one original disc folder.');
      byName.set(file.name, file);
    }
    const sources = [];
    for (let i = 0; i < data.sources.length; i++) {
      const expected = data.sources[i], file = byName.get(expected.name);
      if (!file) fail(`Missing original file: ${expected.name}. Select all BIN files from the supported Japanese disc.`);
      if (file.size !== expected.bytes) fail(`Wrong size: ${expected.name}. Use the original, unmodified Japanese dump.`);
      progress(`Verifying original file ${i + 1} of ${data.sources.length}.`, 5 + 55 * i / data.sources.length);
      if (await sha256(file) !== expected.sha256) fail(`Checksum failed: ${expected.name}. No output was prepared.`);
      sources.push(file);
    }
    progress('Building the Saturn BIN from local files.', 65);
    const parts = data.ops.map(op => op.kind === 'source'
      ? sources[op.index].slice(op.offset, op.offset + op.length)
      : bundle.slice(payload + op.offset, payload + op.offset + op.length));
    const bin = new Blob(parts, {type: 'application/octet-stream'});
    progress('Verifying the complete Saturn BIN. This can take a minute.', 85);
    const actual = await sha256(bin);
    if (actual !== release.binSha256) fail('Output checksum failed. The patch bundle is damaged. No downloads were prepared.');
    const receipt = {
      format: 1, utility: 'Sonic CD Saturn Patcher', version: release.version,
      status: 'verified', bin: {name: release.binName, bytes: bin.size, sha256: actual},
      cue: {name: release.cueName, sha256: release.cueSha256},
      sources: data.sources.map(({name, bytes, sha256}) => ({name, bytes, sha256})),
      hardware_tested: false, processing: 'Local browser. No uploads.'
    };
    progress('Verified. Save both game files in the same SAROO folder.', 100);
    return {bin, cue: new Blob([data.target.cue], {type: 'text/plain'}), receipt};
  }
  return {inspect, apply, sha256};
})();
if (typeof module !== 'undefined') module.exports = SonicPatch;
