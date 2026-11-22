# Easy Patcher completion ledger

Target: accepted V0.082 BIN/CUE. Original dist/ and cd/ remain unchanged.
Game source and Makefile match 49bfd89. Generated game data and SDK boot blobs
are derived. Compiled literals follow the owner's approved provenance rule.

| Gate | Implemented | Verified | Outstanding |
| --- | --- | --- | --- |
| Exact audio | JS Past arithmetic; ffmpeg.wasm for SFX | Seven complete Past tracks, zero residuals; 54 SFX outputs exact; fresh V4 audio stages pass | Chrome receipt |
| Native boundary | WASM hosts, subprocess/ctypes bridge, shared FS, TT schedule | Desktop boundary tests; 336,000 TT values; fresh vendored Pyodide run 54/54 | Chrome runtime loading |
| Format 2 engine | Source/literal/derive, disc roles, derived hashes, fail-closed pipeline | Synthetic contracts; fresh V4 final assembly matches both accepted hashes | Chrome downloads |
| Program provenance | ELF/.i/source/object evidence for nine programs | Zero unclassified bytes; A.BIN derives 62,837 bytes; overlays derive 281,504 bytes | Chrome reconstruction |
| Data serialization | Structs, mixed widths, padding, pointers, strings | 898 native-exact recipes; all 249 CD files match native in fresh V4 | Chrome reconstruction |
| Recipe audit | Strict ownership, source/table slices, SDK boot derivations, exact corpus scan | recipe-v7 audit exit 0; 662,766 literals; 1,938,188,421 corpus bytes; zero matches | None for current recipe |
| Vendored runtimes | 20 pinned files, CI allowance, notices | 50,354,915 bytes; full V4 passes; 1,591 reference paths match pinned Git objects; site-v4 prepared | Live GitHub fetch; Chrome loader |
| Desktop Chrome | Three-input UI, Worker pipeline, pinned GET-only loader | Source and Node checks | BLOCKED: loopback bind EPERM twice; file-mode Chrome SIGABRT before page load twice |
| Closure | Docs and local site packager | Protected paths unchanged; candidate CI checks clean | Fast QA failed after 169/171 passes: copied core approval binds original paths; local commits blocked by Git index permissions |

Private evidence under build/: patcher-pipeline-v4/results.json (fresh 54/54),
patcher-node-image-v1/report.json (accepted hashes), patcher-site-v4 (555 files),
patcher-recipe-v7/recipe.scsp and patcher-recipe-audit-v7/receipt.json.
Fresh script time: 2454.636393418 seconds. Cumulative process peak RSS:
2,760,802,304 bytes. These are Node measurements, not Chrome measurements.

Literal bytes: compiled programs 645,005; ISO structure 11,408; project CD text
18; standalone PoneSound 6,335. Residual bytes: 0. The MIT PoneSound program is
assembled after its pinned SDK baseline is generated. No browser m68k compiler
runs. Six SDK boot blobs are fetched references, not project-owned literals.

Fresh V4 records 2,638 output paths. All final non-metadata outputs match native.
230 diagnostic JSON/stamp hashes differ due to paths, runtime versions,
fingerprints and research-only IR. R3 uses supported --no-scan research mode;
desktop commands retain the scan. This does not satisfy a literal requirement
that every diagnostic report match desktop bytes. Release payloads match.

The Chrome attempts did not load the page. No current browser conversion,
download hash, no-upload proof, live GitHub fetch, publication or new hardware
acceptance is claimed. Earlier format 1 browser evidence is historical.

U.S. input extraction separately passes under vendored Pyodide: 121,366,528
ISO bytes, 1.211 seconds, peak RSS 1,373,241,344 bytes. No network was used.
Fast QA ran in an owned shadow. The visual-mode producer was rejected because
the original approved core profile binds absolute paths in the original checkout.
Copying the three exact receipt files produces the explicit rejection
“Core review does not bind.” The original approvals were not altered.
169 checks pass; visual-mode pixels and credits remain unrun. This is a failed
fast attempt, not a full-suite pass. Original images and all CD files were
rehashed after testing and remain exact. The Chrome crash report places abort()
in macOS application registration; its underlying cause is unproven.

## Verification outside the build sandbox: 2026-11-21 to 2026-11-22

The table above records the sandboxed implementation session. These checks ran
afterwards on the same Mac with network access and installed desktop Chrome.
They supersede the BLOCKED and failed entries above.

| Check | Result |
| --- | --- |
| Desktop Chrome, real discs, package `build/patcher-site-v12` | `PASS: actual Chrome Easy Patcher; downloaded BIN/CUE match accepted V0.082; no uploads` |
| Downloaded BIN, hashed separately | `cb872d149ba3575d9929a1072bb006dd403b97e79dfdfa0a6b4782bf178a3e66` |
| Downloaded CUE, hashed separately | `10f35a87674de372bc4b217a4e877f5321aa683afda91eab18df2df331d04337` |
| Live GitHub fetch | 1,591 of 1,591 pinned files returned the pinned size and SHA-256, each with `access-control-allow-origin: *` (14,378,312 bytes) |
| Fast QA in the working checkout | `PASS` (report under `build/qa-loops/20261121-224851-123883/`) |
| Accepted image and game source | `dist` BIN/CUE hashes unchanged; no diff under `src/` or `Makefile` against `49bfd89` |

Three defects were found by the Chrome runs and fixed:

- The emulator module could not open the U.S. disc, because `Path.resolve()`
  follows the workspace alias into the read-only disc mount. `native.js` now
  mounts that folder into each module.
- The site file list lacked tracked `src/` headers that table recipes read.
- `src/scroll_limits.h` holds disc-derived limits, so the site does not ship it.
  The browser now runs `tools/extract_scroll_limits.py` before packaging. The
  pipeline has 55 steps.

The Chrome run takes about 40 minutes on this Mac. The site is not published.
Firefox, Safari and mobile are untested. The Chrome test fulfils reference
requests from local pinned copies; the live fetch was checked separately.

## Source-only literal policy: 2026-11-22 (current)

This revision supersedes the earlier literal permissions and byte totals above.
The prior Chrome, live-fetch and fast-QA results describe the earlier recipe.
Chrome and commits for this revision belong to the outer session.

All data from build/probe-source/ and src/objects_mm_remaining.inc is derived.
Compiled functions and their literal pools remain allowed. No literal is owned
only by an object file. Compiler VarDecl locations supply source-file and line
evidence. Static storage is checked; assignments and automatic locals cannot
claim a linked data object. Generated initializer bodies also remain DERIVE.
LTO local suffixes are not treated as stable object identities. Ambiguous data
uses a byte-verified source serializer and remains DERIVE.

Host-only Clang queries preserve source markers and offsets while neutralizing
SH assembly and SH ABI assertions. Used layouts and pointer bindings must
reproduce every accepted SH byte. Compiler ASTs and private type spellings are
not included in the recipe. The literal scan joins adjacent literal operations
across owner boundaries, including across zero-length operations.

| Gate | Current result |
| --- | --- |
| Generated data | 1,543 initializers, three linked blobs and 65 strings serialize exactly; no unsupported symbol |
| Source attribution | 200 additional handwritten initializer proofs; zero unresolved program bytes |
| Independent audit | Exit 0; 648,433 literal bytes; 1,938,244,059 corpus bytes; zero matches; all three forbidden-owner counters zero |
| Targeted vendored Pyodide | Initial 4/4 cached stages pass; regenerated MM include and package both pass against fresh converter outputs; Node assembly matches both accepted hashes |
| Fresh vendored Pyodide | PASS 56/56; no generated source files at startup; 2,444.22 seconds; 2,876,932,096 peak RSS bytes |
| Local site | build/patcher-site-source-only-v2; source-only audited recipe; not published |
| Outer-session checks | Chrome and commits not run here; fast QA and live fetch not rerun here |

Literal payload bytes by owner:

| Owner | Bytes |
| --- | ---: |
| compiled-function-and-pools | 594687 |
| project-source-initializer | 13198 |
| compiled-control-table | 1389 |
| source-string | 3545 |
| PoneSound-MIT-program | 6335 |
| dependency-program-string | 4083 |
| compiled-function-constant | 27 |
| dependency-source-initializer | 7408 |
| ISO-structure | 11408 |
| project-CD-text | 18 |
| PoneSound-program | 6335 |

Total: 648,433. CC0-compiled-data, CC0-adapted-program-data and
compiled-object-data: 0 each. SDK/compiler initializer bytes have explicit
non-SEGA source evidence; they are not game art, audio or level data.

Current private evidence: build/patcher-recipe-source-only-v1/recipe.scsp;
build/patcher-recipe-source-only-audit-v1/receipt.json;
build/patcher-source-only-target-image-v2/report.json;
build/patcher-source-only-full-v2/results.json.

A source-based overlap control checks all 1,611 generated-data records against
final literal operations: zero overlapping bytes. The older name-based CC0
classification also covered 41 handwritten project initializers (517 retained
payload bytes). Compiler declarations and complete serialized-byte comparisons
correct those labels. They are not CC0-derived data literals.

The first fresh run passed 54/55 commands, then package.py failed because the
new site file list correctly omitted objects_mm_remaining.inc but no browser
step regenerated it. prepare_mm_remaining.py is now command 55, immediately
before package.py. Its output matches the native include byte-for-byte. The
56-command plan uses the same 1,591 reference paths. The new unseeded full run
passes 56/56 commands. Node assembly verifies all 249 CD payload files and both
accepted image hashes. Receipt: build/patcher-source-only-full-image-v2/report.json.

Per-stage comparisons record 2,405 identical outputs, 241 differences and four
outputs without native peers. Differences include intermediate audio before
Japanese music replacement, JSON diagnostics, a stamp and adapted headers.
Final CD payloads all match; intermediate equality is not claimed. Full evidence:
build/patcher-policy-v1/fresh-summary.json.

## Source-only data policy, verified outside the sandbox: 2026-11-22

Recipe policy `recipe-source-data-and-boot-v3` ships no data table as a literal
unless its initializer is written by hand in tracked project or SDK source.
Tables compiled from the CC0 decompilation and from generated files are rebuilt
in the browser. The pipeline has 56 steps.

| Check | Result |
| --- | --- |
| `tools/audit-recipe.py`, run by the outer session | `PASS: recipe audit; 648433 literal bytes`; 0 unresolved program bytes; 0 matches in a 1,938,244,059-byte corpus |
| Forbidden owner classes | `CC0-compiled-data` 0, `CC0-adapted-program-data` 0, `compiled-object-data` 0 |
| Literal bytes by owner | compiled functions and pools 594,687; project source initializers 13,198; SDK source initializers 7,408; ISO structure 11,408; sound firmware 12,670; strings 7,628; control tables 1,389; other 45 |
| Desktop Chrome, real discs, package `build/patcher-site-outer-1` | `PASS: actual Chrome Easy Patcher; downloaded BIN/CUE match accepted V0.082; no uploads` |
| Downloaded BIN and CUE, hashed separately | `cb872d149ba3575d9929a1072bb006dd403b97e79dfdfa0a6b4782bf178a3e66`, `10f35a87674de372bc4b217a4e877f5321aa683afda91eab18df2df331d04337` |

The audit first failed in the outer session with `Unknown program literal
evidence`. One function listed its two evidence rows in a different order
between runs. The audit now compares evidence rows without regard to order.
Fast QA was not rerun after this change; the change touches recipe, audit and
packaging tools only, and no converter the desktop build runs.


## Contiguous stored-payload audit revision

This revision supersedes the preceding zero-match claims. The old audit joined
some adjacent target operations, but did not cover all adjacency in the stored
payload. A corrected independent rerun reproduces nine matching 16-byte patterns.
This includes seams between twelve-byte project initializer tables and FF runs.

Policy recipe-contiguous-binary-corpus-v4 scans the complete stored payload as
one range after the JSON header. No fill is exempt. Its binary corpus contains
all user disc BINs, the BIOS, cd/ files except .TXT, non-literal compiled-program
ranges and non-text assets/generated files. CUE and generated text are excluded
from the byte test; source provenance covers generated initializers.

Source-copy repair replaces nine patterns at 32 matching payload windows,
spanning 93 literal bytes. Rechecking
after compaction finds zero matches. A bounded repeat loop handles any new seam
created by removal. Ownership totals change only for project-source-initializer,
from 13,198 to 13,105 bytes. Total literals: 648,340. Every other owner total in
the preceding table remains unchanged. All three forbidden owners remain zero.

New tools/audit-site.py scans every built file. Only exact upstream_sha256
matches in the trusted runtime lock skip ownership scanning. File hashes remain
in the receipt. Each other match has a corpus witness, file offset, 16-byte hex
and a generic classification or UNEXPLAINED. Any UNEXPLAINED match fails. Every
match in the literal payload fails, including a fill or text coincidence.

Current private recipe: build/patcher-recipe-contiguous-v2/recipe.scsp.
Independent recipe audit: PASS, exit 0, 1,937,612,811 corpus bytes, zero matches.
Receipt: build/patcher-contiguous-audit-v1/receipt.json.
Site: build/patcher-site-contiguous-v2.
Site audit: build/patcher-site-contiguous-audit-v2/receipt.json; PASS.
547 files scanned; 16 exact upstream files retain hashes and skip ownership scan.
1,197,260 matching windows: 1,110,419 fills; 2,331 ASCII; 84,510 generic runs;
zero UNEXPLAINED; zero recipe payload matches.

The first site scan failed on 81,286 unexplained windows, all in patched Pyodide.
The completed scan retains those matches and certifies each at the identical
byte offset in the local upstream runtime, whose SHA-256 matches the pinned
upstream_sha256. These are unchanged interpreter/lookup-data runs outside the
path patches. They form 81,286 of the generic-run classifications. A changed
window cannot use that proof. The patched file remains scanned in full.
Genesis title-detection strings classify as ASCII. Arithmetic ramps carry an
explicit width, byte order and step explanation. No filename grants an exemption.

Targeted vendored Pyodide: package.py 1/1 PASS, reusing the prior fresh outputs.
Node receipt: build/patcher-contiguous-image-v1/report.json; all 249 CD files and
both accepted BIN/CUE hashes match. Only literal/source operations changed;
no new full converter run was needed. Original native images/CD files are
unchanged. Full report: build/patcher-contiguous-report-v1/REPORT.md.
Chrome and commits belong to the outer session. No network request is made here.

## Contiguous-payload rule, verified outside the sandbox: 2026-11-22

A whole-payload scan by the outer session found nine 16-byte runs shared with
the Japanese data track in the previous recipe. The audit had scanned each
literal range alone, so runs across adjacent ranges were missed. Two runs were
animation script bytes from `src/objects_ss_enemies.inc`; seven were FF fill.
The audit now scans the payload as one buffer with no fill exemption, the
builder replaces every match with a copy from the user's file, and
`tools/audit-site.py` scans every file in a site package.

| Check, run by the outer session | Result |
| --- | --- |
| `tools/audit-recipe.py` on `build/patcher-recipe-contiguous-v2` | `PASS: recipe audit; 648340 literal bytes`; `PASS: literal-run scan; 648340 literal bytes; 1937612811 corpus bytes; 0 matches` |
| Separate whole-payload scan, one range, `--all` | 0 matches against the binary corpus and against the earlier wider corpus |
| `tools/audit-site.py` on `build/patcher-site-outer-2` | `PASS: site ownership audit; 547 scanned files; 16 upstream-identical; 1197260 matches; 0 UNEXPLAINED; 0 recipe payload matches` |
| Explained site matches | fill 1,110,419; ASCII text 2,331; unchanged upstream runtime bytes proven at the same offset 81,286; arithmetic ramps 3,224 |
| Desktop Chrome, real discs, `build/patcher-site-outer-2` | `PASS: actual Chrome Easy Patcher; downloaded BIN/CUE match accepted V0.082; no uploads` |
| Downloaded BIN and CUE, hashed separately | `cb872d149ba3575d9929a1072bb006dd403b97e79dfdfa0a6b4782bf178a3e66`, `10f35a87674de372bc4b217a4e877f5321aa683afda91eab18df2df331d04337` |

The short-table limitation recorded for that revision is closed by the
no-initialized-data revision below. Compiled CC0 functions remain approved code.


## No initialized data literals

Policy recipe-no-initialized-data-v5 supersedes earlier data permissions.
Every source-initialized object in the nine programs derives, including tracked
project tables and SDK/compiler initializers. No table-length exception exists.
856 additional initialized symbols, spanning 38,296 linked bytes, now serialize
from source. This removes 20,513 bytes previously stored under the two source
initializer literal owners. Net initializer recipes rise from 1,543 to 2,317;
82 old all-zero recipes now use zero operations. All source serializers pass.
There are 249 derived string ranges (4,070 bytes including prior ranges).

The source reader expands C macros, active compile branches, enums, sizeof and
late/nested designators. SH GCC DWARF supplies exact SDK layout certificates
and bit-field placement. An independent SH metadata probe independently verifies
the bit serializer. Browser code reads source text with stored layouts; it does
not compile C or receive expanded table values. Every output range has an exact
accepted hash. Unsupported initialized symbols: none.

Final recipe: build/patcher-no-data-recipe-v1/recipe.scsp.
Independent audit: build/patcher-no-data-audit-v1/receipt.json, PASS, exit 0.
The receipt states "initialized data literals: 0" and records all five forbidden
owner counts as zero. Its contiguous scan covers 624,378 payload bytes and
1,937,654,994 corpus bytes with zero matches. Source-copy repair replaces 834
patterns at 4,761 payload windows, removing 6,546 bytes in one pass.

Literal bytes by owner:

| Owner | Bytes | Reason retained |
| --- | ---: | --- |
| compiled-function-and-pools | 594687 | Compiled function instructions and pools |
| compiled-control-table | 1390 | GCC switch/LTO control-flow lowering; no C data initializer |
| compiled-function-constant | 27 | Unnamed instruction constants with R_SH_DIR32 function references |
| source-string | 1844 | Compiler-expanded text without a cheap direct source slice |
| dependency-program-string | 2334 | SDK diagnostic/assertion text without a cheap direct source slice |
| PoneSound-MIT-program | 6335 | Approved linked firmware |
| PoneSound-program | 6335 | Approved standalone firmware |
| ISO-structure | 11408 | Project ISO metadata |
| project-CD-text | 18 | Project CD text |

Total: 624,378. Both source-initializer literal classes: zero. No failed
initializer remains literal under another name. The audit receipt contains
38 range certificates explaining each retained compiler control/constant range,
with source, link-map and code-reference evidence. Their lack of a C initializer
is explicit; they encode compiler-generated control flow or instruction pools.

The lock adds 119 source references (118 SDK files plus hash-pinned GCC source).
Live retrieval of those additions is untested. The new full runner copies from
the built site, validates every source hash, exposes only locked reference files
and derives the U.S. ISO from the supplied BIN. It has no toolchain mount.

Site: build/patcher-site-no-data-v1. Fresh full run:
build/patcher-no-data-full-v2: PASS 56/56, using vendored Pyodide/runtime files
from that site. Wall time 3,121.52 seconds; peak process RSS 2,594,160,640 bytes.
The first attempt stopped before conversion on a test-runner initialization
error; the fix moves its hash helper before the new source checks. No old pass
is claimed for this fresh run.
Final Node receipt: build/patcher-no-data-image-v1/report.json; PASS, all 249 CD
files and both accepted V0.082 hashes match. Native BIN/CUE and CD files remain
unchanged; src/ and Makefile still match 49bfd89.
Site audit: build/patcher-site-no-data-audit-v1/receipt.json; PASS. It scans 549
files; 16 files are upstream-identical. Matches: fill 1,110,778; ASCII 10,629;
generic 84,946 (including 81,722 same-offset upstream proofs); UNEXPLAINED zero;
recipe payload matches zero. Full report: build/patcher-no-data-report-v1/REPORT.md.
Per-stage results contain 2,405 native-equal outputs and 241 intermediate or
diagnostic differences. All final CD payload hashes match; intermediate equality
is not claimed. No new full game QA or hardware acceptance is claimed.
SDK Node 22.16.0 is used because the local Homebrew Node loader is broken.
No network, staging, commit, Chrome run or publication is performed here.

## No initialized data in the bundle, verified outside the sandbox: 2026-11-22

Recipe policy `recipe-no-initialized-data-v5`. Every initialized data object in
the nine programs is rebuilt in the browser from source text. The outer session
ran these checks on `build/patcher-no-data-recipe-v1` and
`build/patcher-site-outer-3`.

| Check | Result |
| --- | --- |
| `tools/audit-recipe.py` | `PASS: recipe audit; 624378 literal bytes`; `PASS: literal-run scan; 624378 literal bytes; 1937654994 corpus bytes; 0 matches` |
| Literal bytes in the five data owner classes | 0 each |
| Literal bytes by owner | compiled functions and pools 594,687; compiler switch tables 1,390; instruction constants 27; diagnostic strings 4,178; sound firmware 12,670; ISO structure 11,408; CD text 18 |
| Separate whole-payload scan, one range, `--all` | 0 matches against both corpus definitions |
| `tools/audit-site.py` | `PASS: site ownership audit; 549 scanned files; 16 upstream-identical; 1206353 matches; 0 UNEXPLAINED; 0 recipe payload matches` |
| Desktop Chrome, real discs | `PASS: actual Chrome Easy Patcher; downloaded BIN/CUE match accepted V0.082; no uploads` |
| Downloaded BIN and CUE, hashed separately | `cb872d149ba3575d9929a1072bb006dd403b97e79dfdfa0a6b4782bf178a3e66`, `10f35a87674de372bc4b217a4e877f5321aa683afda91eab18df2df331d04337` |

This removes the earlier limit about short hand-written tables. What remains
literal is compiled code, compiler-generated tables, diagnostic strings, the
MIT sound firmware and the ISO structure. Compiled functions include code
compiled from the CC0 decompilation; rebuilding that in the browser needs an
SH-2 compiler there.
