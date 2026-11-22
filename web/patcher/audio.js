'use strict';
// Integer PCM input, double fade gain, float32 filter result, signed-32 conversion.
// This follows the accepted desktop ffmpeg chain without platform SIMD rounding.
const SonicAudio = (() => {
  const clip = (x, low, high) => Math.min(high, Math.max(low, x));
  function pastFade(bytes) {
    if (!(bytes instanceof Uint8Array) || bytes.byteLength % 4) throw new Error('Past PCM must be stereo s16le.');
    const frames = bytes.byteLength / 4, range = 3 * 44100;
    if (frames < range) throw new Error('Past PCM is shorter than the fade.');
    const start = frames - range;
    const output = new Uint8Array(Math.ceil(bytes.byteLength / 2352) * 2352);
    const input = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    const result = new DataView(output.buffer);
    for (let i = 0; i < frames * 2; i++) {
      const x = input.getInt16(i * 2, true), frame = Math.floor(i / 2);
      let y;
      if (frame < start) y = clip(Math.floor(x * 1.5 + .5), -32768, 32767);
      else {
        const gain = clip((range - (frame - start)) / range, 0, 1);
        const product = Math.fround(x * 1.5 / 32768 * gain);
        // The accepted ARM conversion truncates here. Round-to-even differs
        // at one R3 sample even though it happens to match the entire PPZ track.
        const signed = clip(Math.trunc(product * 2147483648), -2147483648, 2147483647);
        y = clip(Math.floor((signed + 32768) / 65536), -32768, 32767);
      }
      result.setInt16(i * 2, y, true);
    }
    return output;
  }
  return {pastFade};
})();
if (typeof module !== 'undefined') module.exports = SonicAudio;
