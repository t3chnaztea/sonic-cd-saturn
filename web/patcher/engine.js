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
  // The recipe pins one U.S. image, sonic.bin/sonic.cue (a chdman extraction).
  // The common Redump "Sonic CD (USA)" set has 35 split tracks with the same
  // audio. Rebuild the pinned layout from it: keep track 1, join tracks 2-35,
  // drop the first 353,920 bytes of that audio (the 150-sector track 2 pregap
  // plus a 280-sample read offset) and append 1,120 zero bytes. The pinned
  // size and SHA-256 checks still decide whether the result is accepted.
  const US_CUE = "FILE \"sonic.bin\" BINARY\n  TRACK 01 MODE1/2352\n    INDEX 01 00:00:00\n  TRACK 02 AUDIO\n    PREGAP 00:02:00\n    INDEX 01 13:10:11\n  TRACK 03 AUDIO\n    INDEX 00 13:14:25\n    INDEX 01 13:16:25\n  TRACK 04 AUDIO\n    INDEX 00 15:05:39\n    INDEX 01 15:07:39\n  TRACK 05 AUDIO\n    INDEX 00 16:27:42\n    INDEX 01 16:29:42\n  TRACK 06 AUDIO\n    INDEX 00 17:53:52\n    INDEX 01 17:55:52\n  TRACK 07 AUDIO\n    INDEX 00 19:34:57\n    INDEX 01 19:36:57\n  TRACK 08 AUDIO\n    INDEX 00 20:55:62\n    INDEX 01 20:57:62\n  TRACK 09 AUDIO\n    INDEX 00 22:18:63\n    INDEX 01 22:20:63\n  TRACK 10 AUDIO\n    INDEX 00 24:15:00\n    INDEX 01 24:17:00\n  TRACK 11 AUDIO\n    INDEX 00 25:36:02\n    INDEX 01 25:38:02\n  TRACK 12 AUDIO\n    INDEX 00 26:55:06\n    INDEX 01 26:57:06\n  TRACK 13 AUDIO\n    INDEX 00 28:39:10\n    INDEX 01 28:41:10\n  TRACK 14 AUDIO\n    INDEX 00 29:58:43\n    INDEX 01 30:00:43\n  TRACK 15 AUDIO\n    INDEX 00 31:04:55\n    INDEX 01 31:06:55\n  TRACK 16 AUDIO\n    INDEX 00 32:37:58\n    INDEX 01 32:39:58\n  TRACK 17 AUDIO\n    INDEX 00 33:40:68\n    INDEX 01 33:42:68\n  TRACK 18 AUDIO\n    INDEX 00 35:01:74\n    INDEX 01 35:03:74\n  TRACK 19 AUDIO\n    INDEX 00 36:58:09\n    INDEX 01 37:00:09\n  TRACK 20 AUDIO\n    INDEX 00 38:12:19\n    INDEX 01 38:14:19\n  TRACK 21 AUDIO\n    INDEX 00 39:20:25\n    INDEX 01 39:22:25\n  TRACK 22 AUDIO\n    INDEX 00 40:46:32\n    INDEX 01 40:48:32\n  TRACK 23 AUDIO\n    INDEX 00 41:53:39\n    INDEX 01 41:55:39\n  TRACK 24 AUDIO\n    INDEX 00 43:07:45\n    INDEX 01 43:09:45\n  TRACK 25 AUDIO\n    INDEX 00 44:28:49\n    INDEX 01 44:30:49\n  TRACK 26 AUDIO\n    INDEX 00 45:53:50\n    INDEX 01 45:55:50\n  TRACK 27 AUDIO\n    INDEX 00 46:24:51\n    INDEX 01 46:26:51\n  TRACK 28 AUDIO\n    INDEX 00 46:55:52\n    INDEX 01 46:57:52\n  TRACK 29 AUDIO\n    INDEX 00 47:06:12\n    INDEX 01 47:08:12\n  TRACK 30 AUDIO\n    INDEX 00 47:30:13\n    INDEX 01 47:32:13\n  TRACK 31 AUDIO\n    INDEX 00 47:53:51\n    INDEX 01 47:55:51\n  TRACK 32 AUDIO\n    INDEX 00 48:06:52\n    INDEX 01 48:08:52\n  TRACK 33 AUDIO\n    INDEX 00 50:09:62\n    INDEX 01 50:11:62\n  TRACK 34 AUDIO\n    INDEX 00 52:14:71\n    INDEX 01 52:16:71\n  TRACK 35 AUDIO\n    INDEX 00 53:47:73\n    INDEX 01 53:49:73\n";
  const US_HELP = 'Use the Redump "Sonic CD (USA)" dump: its CUE and all 35 BIN tracks.';
  function splitUS(files) {
    const us = files.filter(f => f && f.file && f.role === 'us');
    if (us.some(f => f.file.name.toLowerCase() === 'sonic.bin')) return files;
    const tracks = [];
    for (const {file} of us) {
      const m = /\(Track (\d+)\)\.bin$/i.exec(file.name);
      if (m) tracks[Number(m[1])] = file;
    }
    if (!tracks.length) return files;
    if (tracks.length !== 36) fail(`The U.S. disc needs 35 BIN tracks. ${US_HELP}`);
    for (let n = 1; n <= 35; n++) if (!tracks[n]) fail(`Missing U.S. BIN track ${n}. ${US_HELP}`);
    const audio = new Blob(tracks.slice(2)).slice(353920);
    const bin = new File([tracks[1], audio, new Uint8Array(1120)], 'sonic.bin');
    const cue = new File([US_CUE], 'sonic.cue', {type: 'text/plain'});
    return files.filter(f => !(f && f.file && f.role === 'us')).concat([{role: 'us', file: bin}, {role: 'us', file: cue}]);
  }
  const DISC = {jp: ['the supported Japanese disc', 'Select the CUE and all 35 BIN tracks from the supported Japanese disc.'],
    us: ['the U.S. disc', US_HELP], bios: ['the U.S. Sega CD BIOS', 'Select the Sega CD Model 2 U.S. BIOS v2.00W, 131,072 bytes, any filename.']};
  const BIOS_UNSUPPORTED = 'The Model 1 (v1.10) BIOS and other revisions are not supported.';
  const disc = r => DISC[r] || DISC.jp;
  async function sha256(blob) {
    const digest = await crypto.subtle.digest('SHA-256', await blob.arrayBuffer());
    return Array.from(new Uint8Array(digest), x => x.toString(16).padStart(2, '0')).join('');
  }
  const hex = digest => Array.from(new Uint8Array(digest), x => x.toString(16).padStart(2, '0')).join('');
  // The BIOS is matched by size and SHA-256 under any filename. Some dumps
  // store each 16-bit word with its two bytes swapped. A size match with a
  // hash miss is swapped in memory and checked once more. Only the pinned
  // revision passes either check.
  async function matchBios(file, expected) {
    if (file.size !== expected.bytes) fail(`Wrong size: the selected BIOS is not ${expected.bytes.toLocaleString('en-US')} bytes. ${DISC.bios[1]} ${BIOS_UNSUPPORTED}`);
    const bytes = new Uint8Array(await file.arrayBuffer());
    if (hex(await crypto.subtle.digest('SHA-256', bytes)) !== expected.sha256) {
      for (let i = 0; i + 1 < bytes.length; i += 2) { const x = bytes[i]; bytes[i] = bytes[i + 1]; bytes[i + 1] = x; }
      if (hex(await crypto.subtle.digest('SHA-256', bytes)) !== expected.sha256) fail(`Checksum failed: the selected BIOS is not the Sega CD Model 2 U.S. BIOS v2.00W. ${BIOS_UNSUPPORTED} No output was prepared.`);
    }
    return new File([bytes], expected.name);
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
    const byName = new Map(), biosFiles = [];
    files = splitUS(Array.from(files));
    for (const selected of files) {
      const file = selected.file || selected, selectedRole = selected.file ? selected.role : undefined;
      if (!role(selectedRole)) fail('An input has an unsupported disc role.');
      const key = `${selectedRole || ''}:${file.name}`;
      if (selectedRole === 'bios') { biosFiles.push(file); continue; }
      if (byName.has(key)) fail('Two selected files have the same name. Choose one original disc folder.');
      byName.set(key, file);
    }
    const sources = [];
    for (let i = 0; i < data.sources.length; i++) {
      const expected = data.sources[i];
      if (expected.role === 'bios') {
        if (biosFiles.length > 1) fail(`Select one BIOS file only. ${DISC.bios[1]}`);
        if (!biosFiles.length) fail(`Missing original file: ${DISC.bios[0]}. ${DISC.bios[1]}`);
        progress(`Verifying original file ${i + 1} of ${data.sources.length}.`, 5 + 55 * i / data.sources.length);
        sources.push(await matchBios(biosFiles[0], expected));
        continue;
      }
      const file = byName.get(`${expected.role || ''}:${expected.name}`);
      if (!file) fail(`Missing original file from ${disc(expected.role)[0]}: ${expected.name}. ${disc(expected.role)[1]}`);
      if (file.size !== expected.bytes) fail(`Wrong size: ${expected.name} from ${disc(expected.role)[0]}. ${disc(expected.role)[1]}`);
      progress(`Verifying original file ${i + 1} of ${data.sources.length}.`, 5 + 55 * i / data.sources.length);
      if (await sha256(file) !== expected.sha256) fail(`Checksum failed: ${expected.name} from ${disc(expected.role)[0]}. ${disc(expected.role)[1]} No output was prepared.`);
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
  return {inspect, apply, sha256, splitUS};
})();
if (typeof module !== 'undefined') module.exports = SonicPatch;
