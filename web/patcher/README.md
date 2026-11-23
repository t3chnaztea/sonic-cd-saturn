# Sonic CD Saturn Easy Patcher

The page takes three groups of local files: the supported Japanese split-track
BIN/CUE, the supported U.S. BIN/CUE, and the U.S. Sega CD BIOS. A Web Worker runs
Python converters and local WebAssembly tools. Download links require the
accepted V0.082 hashes:

- BIN: cb872d149ba3575d9929a1072bb006dd403b97e79dfdfa0a6b4782bf178a3e66
- CUE: 10f35a87674de372bc4b217a4e877f5321aa683afda91eab18df2df331d04337

Implementation and verification gates are tracked in
[IMPLEMENTATION.md](IMPLEMENTATION.md). A prepared site package requires a
passing audit. Source files alone do not provide a recipe.scsp deployment file.
No site package or release has been published by this work.

## Inputs and operation

Use current desktop Chrome. Allow at least 4 GiB of spare memory. Mobile,
Firefox and Safari conversion are unverified. The output is 759,063,312 bytes.

Select the Japanese CUE plus all 35 original BIN tracks. For the U.S. disc,
select the CUE and all 35 BIN tracks of the Redump "Sonic CD (USA)" dump. The
page joins those tracks into the pinned single-BIN layout (sonic.bin and
sonic.cue) before any check: it keeps track 1, drops the first 353,920 audio
bytes (the track 2 pregap plus a 280-sample read offset) and appends 1,120 zero
bytes. A matching single sonic.bin and sonic.cue are still accepted. Select the
Sega CD Model 2 U.S. BIOS v2.00W (131,072 bytes, SHA-256
b1c2036b79467514eaaa69c76e5ba83801621e821059caa53cb921a0b21e3af4) under any
filename. The page matches the BIOS by length and SHA-256. A byte-swapped copy
is swapped back in memory and must then match the same hash. The Model 1
(v1.10) BIOS and other revisions are not supported. Disc filenames, lengths
and SHA-256 values must match the recipe. CHD, ZIP, patched images and other
revisions are unsupported. The original files are mounted read-only.

Select **Verify and patch**. The page verifies user inputs before loading the
conversion pipeline. It fetches pinned reference files from GitHub, checks
per-file hashes, runs the converters, fills generated program-data ranges,
constructs the fixed ISO layout and encodes its sectors. The final BIN and CUE
must match release.js before links appear. Save both files together in one
SAROO/ISO folder. The receipt records software verification, not a console test.

**Cancel** terminates the Worker. Changing an input clears old download links.
Step 23 reports the current zone and task through 16 background-table substeps.
Its progress bar advances after real substeps complete. A long substep can still
take several minutes. Refreshing the page discards the conversion in progress.
The page shows total elapsed time, time since the last progress message, and a
timestamped running log. Step 23 has a 17-minute countdown based on the recorded
M4 run. This is an estimate. Reaching zero does not cancel the conversion.
The clock runs on the page while the conversion worker is busy. Only actual
worker messages enter the log or advance the progress bar. Cancel and errors
freeze the clocks. A new run clears the log. The log keeps the latest250 entries.
The fast presentation check is `tools/test-patcher-activity-ui.cjs`; it uses
simulated worker messages and does not convert game data.
The page has no account, analytics, external fonts or upload endpoint. Reference
requests contain only fixed public repository paths and commit IDs. A separate
check on 2026-11-22 fetched all 1,591 pinned files from GitHub with the pinned
sizes and hashes. Offline tests fulfill those requests from the pinned local
copies.

## Local package preparation

The accepted native image, ELF, preprocessor outputs and converter outputs must
already exist. These tools read them without rebuilding the game. All output
paths below must be new directories under ignored build/.

    python3 tools/make-recipe-bundle.py --out build/recipe-raw-new
    python3 tools/audit-recipe.py build/recipe-raw-new/recipe.scsp \
      --work build/recipe-raw-audit-new
    python3 tools/source-recipe-literals.py build/recipe-raw-new/recipe.scsp \
      --audit build/recipe-raw-audit-new --out build/recipe-candidate-new
    python3 tools/audit-recipe.py build/recipe-candidate-new/recipe.scsp \
      --work build/recipe-audit-new
    python3 tools/make-pipeline-lock.py \
      --reads build/patcher-pipeline-new/source-files-used.json \
      --recipe build/recipe-candidate-new/recipe.scsp
    python3 tools/make-patcher-site.py \
      --recipe build/recipe-candidate-new/recipe.scsp \
      --audit build/recipe-audit-new/receipt.json --out build/easy-patcher-site-new
    python3 -m http.server 8082 --bind 127.0.0.1 \
      --directory build/easy-patcher-site-new

Open http://127.0.0.1:8082/web/patcher/. The package builder copies only the named
runtimes, hash-checked project source files and an audited recipe. It copies no
reference checkout, BIOS, disc image or converter output. The reconstruction
recipe stays under build/ and is never committed. A failing audit cannot create
a prepared site package. Publishing remains a separate action.

The raw audit must reach its literal-run scan. Only exact 16-byte coincidence
matches can be replaced by source-recipe-literals.py. Other audit failures need
correction before that step. The final candidate requires its own passing audit.

## Program-data provenance and audit

The builder reads the accepted ELF and compiler .i line markers. It includes
all nine program files, including the zone overlays. Every initialized data
object derives from source, including handwritten project tables, SDK/compiler
initializers and CC0-derived data. No short-table exception exists. The browser
reads tracked source or pinned fetched source and serializes it to the accepted
layout. Linked game assets also derive. Zero fill stores no payload bytes.

Literals contain compiled function code and pools, remaining compiler-generated
strings, PoneSound firmware, ISO structure and project CD text. Compiler switch
lowering and unnamed instruction constants have no C data-object initializer;
the audit records each retained range with its source, link-map or R_SH_DIR32
code references and an explicit reason. Object filenames grant no ownership.

Compiler VarDecl records locate source initializers. Source macros and enums
are expanded deterministically in Python. The SH GCC compiler supplies SDK
layout metadata, including bit fields; no compiler runs in the browser. Every
serialized object must match the complete accepted byte range. Host ASTs,
metadata objects and expanded initializer values are absent from the recipe.

The serializer supports arrays, structs, unions, mixed widths, zero fill and
relocated pointers. Schemas contain field offsets and sizes. Pointer records
contain linked addresses and relocation/source evidence. Converter table values
are read again at runtime; the bundle carries none of them. Every reconstructed
range and final file has a pinned hash. No audio residual is needed: the seven
Past fades use an exact arithmetic implementation; SFX uses ffmpeg.wasm.

The audit reruns certification. It rejects generated-data literals,
unclassified bytes, changed recipes and unowned payload bytes. Its exact
16-byte-run scan covers user discs/BIOS, CD game-data files and generated assets.
The byte-test corpus contains every user disc BIN, the BIOS, non-text generated
assets and CD files except .TXT. CUE and generated text (.inc/.h/.json/.c) are
excluded from this binary test; source provenance still covers generated text.
For compiled CD programs, the corpus includes non-literal ranges. Approved program
ranges are excluded to avoid comparing a literal with itself in A.BIN. Project
CD text metadata is separate from game-data files. Long zero runs use zero-fill
operations rather than literal bytes. A nonzero audit exit blocks distribution.
The entire literal payload is scanned as one stored contiguous buffer, starting
after the JSON header. Target operations, ownership records, zero fills and
derivations cannot split it. Every matching 16-byte window fails, including
single-byte fills. The repair tool rechecks after compaction and repeats until
zero matches remain; exact source copies replace matched bytes. The audit rejects the legacy
CC0-compiled-data, CC0-adapted-program-data, compiled-object-data,
project-source-initializer and dependency-source-initializer permissions.

The no-initialized-data policy receipt records **624,378 literal bytes**:

| Owner | Bytes |
| --- | ---: |
| compiled-function-and-pools | 594687 |
| compiled-control-table | 1390 |
| source-string | 1844 |
| PoneSound-MIT-program (linked firmware) | 6335 |
| dependency-program-string | 2334 |
| compiled-function-constant | 27 |
| ISO-structure | 11408 |
| project-CD-text | 18 |
| PoneSound-program (standalone firmware) | 6335 |

All five forbidden owner totals are zero. The receipt states
"initialized data literals: 0". It also lists each compiler code-constant reason. Source evidence accompanies every
literal record. The current validation state is in IMPLEMENTATION.md.

The separate site audit scans every built file, including the recipe JSON,
project source, patched Pyodide and locally built WASM. A runtime skips ownership
scanning only when its actual SHA-256 equals upstream_sha256 in the checkout's
pinned runtime lock. Each skipped file retains its hash in the receipt. Every
other match records file/offset, exact 16-byte hex, a corpus witness and a
classification: fill, ASCII text, generic run with an explanation, or UNEXPLAINED.
Any UNEXPLAINED match fails. Any match overlapping the recipe literal payload
fails regardless of its classification. No filename grants an exemption.

    python3 tools/audit-site.py build/site-new \
      --audit build/recipe-audit-new --work build/site-audit-new \
      --upstream .deps/pyodide-spike-0.27.7/extracted/pyodide/pyodide.asm.wasm

The audit work directory must be new. --audit names a passing v5 recipe audit
whose corpus manifest supplies the identical binary corpus. Receipts stay local.
An optional --upstream file must match a recorded upstream SHA-256. It grants no
file exemption. For a pinned patched runtime, a matching window can receive a
generic-runtime explanation only if its exact bytes match the same upstream
offset. Each such match records the upstream hash and offset. This certifies
unchanged interpreter code and lookup data outside the diagnostic-path patches.
The patched Pyodide file remains scanned in full. Genesis title-detection text
is classified as ASCII; counting ramps carry their arithmetic explanation.

## Runtime pins and tests

Runtime versions, archive hashes, file hashes and licenses are recorded in
vendor/runtime-lock.json and [THIRD-PARTY.md](../../THIRD-PARTY.md). Pyodide,
Pillow, ffmpeg and the native-tool WASM hosts are served from the same site.
No CDN is used. CI's vendor allowance requires exact hashes and filenames.

    node tools/test-browser-patch.cjs
    python3 tools/test_native.py
    python3 tools/test_recipe_literal_scan.py
    python3 tools/test_recipe_provenance.py
    node tools/test-past-fade.cjs build/past-fade-check-new
    node tools/test-browser-patch-ui.cjs \
      build/easy-patcher-site-new build/easy-patcher-chrome-new

The Chrome test requires an installed Chrome and an existing Playwright module.
PLAYWRIGHT_MODULE may point to that module. It performs fresh conversion from
real files, downloads the BIN/CUE and checks both hashes. GitHub requests are
fulfilled from local pinned checkouts; live fetch is not claimed. It checks bad
BIOS input, cancellation, layouts, stale-link removal and absence of uploads.
It installs no browser. Receipts, screenshots and downloads stay under build/.

The offline Node runner uses the same locked source file list and 56 commands
as the browser. Generated source files are absent at fresh-run startup. A
targeted run may reuse converter outputs with --seed and --script; its image
test must use --diagnostic. The --site option copies project files from the actual built site, checks every
locked hash, exposes only locked references, and extracts the U.S. ISO from the
user BIN. It has no toolchain mount. Only an unseeded complete run receives a fresh-run
image receipt from tools/test-recipe-image.cjs.

The source serializer lock adds 119 references: 118 libyaul source/header files
at its existing pinned commit plus GCC 13.4.0 libgcc2.c. The GCC release URL has
an exact content SHA-256 pin. Local tests use the existing source files. Live
retrieval of these added references is untested in this offline session.

## SCSP format 2

The envelope is SCSP082 plus newline, a four-byte little-endian JSON header
length, JSON metadata, then approved program/ISO literals. Ordered target
operations are source, literal or derive. Sources have disc roles, filenames,
sizes and hashes. Each derive names an output file with a size and SHA-256.
Construction metadata describes program serializers, zero fill, literals and
ISO file extents. It contains no derive output. Bounds and final hashes are
checked before download links appear. Format 1 remains in synthetic engine
tests only; its private bundles contain converted data and must not be shared.

The six SDK boot/security blobs also remain DERIVE. The browser fetches their
pinned reference files; the site package includes none of their bytes. Program
literal coincidences found by the 16-byte scan become exact original-input,
converter-output or serialized-table slices. Ownership proofs are deduplicated
as metadata. They contain no converted bytes or residual correction values.
