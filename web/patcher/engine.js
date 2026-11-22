'use strict';
// Local source/literal/derive recipes. Downloads require the release hashes.
const SonicPatch = (() => {
  const MAGIC = 'SCSP082\n';
  const fail = message => { throw new Error(message); };
  const integer = n => Number.isSafeInteger(n) && n >= 0;
  const hash = s => typeof s === 'string' && /^[a-f0-9]{64}$/.test(s);
  const name = s => typeof s === 'string' && s.length > 0 && s.length < 256 && !/[\\/\x00-\x1f]/.test(s);
  const relative = s => typeof s === 'string' && s.length > 0 && s.length < 256 &&
    !/[\\\x00-\x1f]/.test(s) && s.split('/').every(p => p && p !== '.' && p !== '..');
  const role = s => s === undefined || ['jp', 'us', 'bios'].includes(s);
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
    if (![1, 2].includes(data?.format) || data.version !== release.version || !Array.isArray(data.sources) || !data.sources.length || data.sources.length > 128 || !Array.isArray(data.ops) || !data.ops.length || data.ops.length > 400000) fail('The patch format or release is unsupported.');
    const target = data.target;
    if (!target || target.bytes !== release.binBytes || target.sha256 !== release.binSha256 || target.cue_sha256 !== release.cueSha256 || typeof target.cue !== 'string' || target.cue.length > 16384) fail('This bundle does not produce the accepted V0.082 release.');
    if (await sha256(new Blob([target.cue])) !== release.cueSha256) fail('The output CUE checksum failed.');
    const names = new Set();
    for (const source of data.sources) {
      const key = `${source?.role || ''}:${source?.name}`;
      if (!source || !name(source.name) || !role(source.role) || names.has(key) || !integer(source.bytes) || !source.bytes || source.bytes > 2 ** 31 || !hash(source.sha256)) fail('The patch has an invalid or repeated source file.');
      names.add(key);
    }
    const derived = new Map();
    if (data.format === 2) {
      if (!Array.isArray(data.derivations) || !data.derivations.length || data.derivations.length > 20000) fail('The derivation manifest is invalid.');
      for (const file of data.derivations) {
        if (!file || !relative(file.name) || derived.has(file.name) || !integer(file.bytes) || !file.bytes || !hash(file.sha256)) fail('The derivation manifest contains an invalid file.');
        derived.set(file.name, file);
      }
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
      else if (op.kind === 'derive' && data.format === 2 && derived.has(op.file)) limit = derived.get(op.file).bytes;
      else fail('The patch has an unsupported operation.');
      if (!integer(op.offset + op.length) || op.offset + op.length > limit) fail('The patch range exceeds its file.');
      total += op.length;
      if (!integer(total) || total > release.binBytes) fail('The patch output is too large.');
    }
    if (total !== release.binBytes) fail('The patch output is incomplete.');
    return {data, payload};
  }
  async function apply(bundle, files, release, progress = () => {}, pipeline) {
    progress('Reading the patch bundle.', 1);
    const {data, payload} = await inspect(bundle, release);
    const byName = new Map();
    for (const selected of files) {
      const file = selected.file || selected, selectedRole = selected.file ? selected.role : undefined;
      if (!role(selectedRole)) fail('An input has an unsupported disc role.');
      const key = `${selectedRole || ''}:${file.name}`;
      if (byName.has(key)) fail('Two selected files have the same name. Choose one original disc folder.');
      byName.set(key, file);
    }
    const sources = [];
    for (let i = 0; i < data.sources.length; i++) {
      const expected = data.sources[i], file = byName.get(`${expected.role || ''}:${expected.name}`);
      if (!file) fail(`Missing original file: ${expected.name}. Select all BIN files from the supported Japanese disc.`);
      if (file.size !== expected.bytes) fail(`Wrong size: ${expected.name}. Use the original, unmodified Japanese dump.`);
      progress(`Verifying original file ${i + 1} of ${data.sources.length}.`, 5 + 55 * i / data.sources.length);
      if (await sha256(file) !== expected.sha256) fail(`Checksum failed: ${expected.name}. No output was prepared.`);
      sources.push(file);
    }
    const derived = new Map();
    if (data.format === 2) {
      if (typeof pipeline !== 'function') fail('This recipe requires the verified conversion pipeline.');
      const produced = await pipeline(data, sources, progress);
      if (!(produced instanceof Map)) fail('The conversion pipeline returned an invalid result.');
      for (const expected of data.derivations) {
        const file = produced.get(expected.name);
        if (!(file instanceof Blob) || file.size !== expected.bytes) fail(`Derived file size failed: ${expected.name}.`);
        if (await sha256(file) !== expected.sha256) fail(`Derived file checksum failed: ${expected.name}.`);
        derived.set(expected.name, file);
      }
    }
    progress('Building the Saturn BIN from local files.', 65);
    const parts = data.ops.map(op => op.kind === 'source'
      ? sources[op.index].slice(op.offset, op.offset + op.length)
      : op.kind === 'derive' ? derived.get(op.file).slice(op.offset, op.offset + op.length)
        : bundle.slice(payload + op.offset, payload + op.offset + op.length));
    const bin = new Blob(parts, {type: 'application/octet-stream'});
    progress('Verifying the complete Saturn BIN. This can take a minute.', 85);
    const actual = await sha256(bin);
    if (actual !== release.binSha256) fail('Output checksum failed. The patch bundle is damaged. No downloads were prepared.');
    const receipt = {
      format: data.format, utility: 'Sonic CD Saturn Easy Patcher', version: release.version,
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
