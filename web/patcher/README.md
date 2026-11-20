# Sonic CD Saturn Patcher

Local V0.082 preview with numbered steps, direct copy, and verified downloads. This site uses CSS and text. It has no game art, external fonts, analytics, or upload service.

## Run locally

From the repository root:

```sh
python3 -m http.server 8082 --bind 127.0.0.1 --directory web/patcher
```

Open `http://127.0.0.1:8082` in current desktop Chrome. Firefox and Safari are unverified. Web Workers and secure-context Web Crypto are required. Keep about 2 GiB of memory available. The output is 759,063,312 bytes (724 MiB).

Choose a private `.scsp` bundle. Select all original Japanese split-track BIN files. The bundle lists the exact filenames, sizes, and SHA-256 hashes it supports. The local test uses 34 of the 35 Japanese tracks. Selecting all 35 is safe. CHD, combined BIN, ZIP, renamed tracks, other revisions, and modified files are unsupported.

Select **Verify and patch**. Required inputs are hashed first. Copy and literal ranges form a new Blob. The complete output is hashed in a worker. The accepted BIN and CUE hashes are pinned in `release.js`. Download links appear only after both hashes match. Save the BIN and CUE together in a new `SAROO/ISO` folder. The JSON receipt records verification. It does not claim hardware acceptance.

**Cancel** terminates the worker. Changing an input removes prior download links. Original files are never opened for writing.

## Private bundle preparation

The accepted native image must already exist. This command reads it without rebuilding:

```sh
nice -n 20 python3 tools/make-browser-patch.py \
  --out build/local-preview-v0082.private.scsp
```

The generator resolves `assets/private/sonic-cd-japan.cue`, reads its original BIN tracks, and uses `dist/sonic-cd-saturn-prototype.{bin,cue}`. The output must be new and stay under ignored `build/`. A receipt records its hash. Identical 2352-byte sectors become source copies. Nonmatching target bytes become private literals.

**Do not distribute this bundle.** The tested bundle has 446,494,272 copied bytes and 312,569,040 literal bytes. Some literals contain transformed game data. A delta is not proof that a file is safe to publish. Keep the bundle on the owner's storage. `.scsp` files are ignored and rejected by the export audit and asset-free CI.

## Public release boundary

This directory contains code and release metadata only. It is a working local patcher preview. It is not a complete public patch distribution. It neither downloads nor embeds a payload.

Before a public installer can ship, replace private literals with an extraction/conversion route that obtains SEGA data from the user's own files. Audit every distributed payload and its licenses. Prove its output against a named accepted build. A separate source audit is required before publishing the full repository. Do not publish the current local Git history or bypass a failed export audit.

No payload is published. The public route today is the source build in the repository README.

## Tests

Asset-free contracts:

```sh
node tools/test-browser-patch.cjs
```

Actual desktop Chrome test, with Playwright already available:

```sh
nice -n 20 node tools/test-browser-patch-ui.cjs \
  build/local-preview-v0082.private.scsp build/browser-patch-test-new
```

`PLAYWRIGHT_MODULE` may point to an existing Playwright module. `BROWSER_CHANNEL` defaults to installed `chrome`. No browser is installed. The test serves only six allowlisted site files on loopback. It never serves the bundle or disc tracks. It checks invalid input, cancel, a real worker patch, downloaded hashes, receipt, desktop and 390 px layouts, stale link removal, no uploads, and browser errors. Screenshots and downloads stay under `build/`. Failed runs stay separate.

## SCSP format 1

Eight ASCII bytes `SCSP082` plus newline; a four-byte little-endian JSON header length; UTF-8 JSON; then literal bytes. The header contains version, source filename/size/SHA-256 rows, target size/SHA-256/CUE text/CUE SHA-256, and ordered operations. A `source` operation has an index, offset, and length. A `literal` operation has an offset into the payload and a length. All ranges must use safe nonnegative integers and fit their files. The total output size must match the pinned release. Unknown operations fail. Header size, source count, and operation count have limits.

Web Crypto hashes whole Blob buffers. This version is verified on the current 24 GiB Mac. It makes no low-memory or mobile patching claim. It has no compression engine or third-party JavaScript dependency. The code uses the repository's MIT license. It grants no rights to SEGA data.
