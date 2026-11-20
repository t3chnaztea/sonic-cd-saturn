#!/usr/bin/env python3
"""Assemble a shareable, source-only release package.

The package holds project docs, build instructions, the SHA-256 of the
tested BIN (hash only) and a manifest. It never holds a disc BIOS, audio, or anything from assets/, dist/ or build/. Every file is
checked by name, location and content before it is copied, and the staged
folder is checked again before it is zipped.

    python3 tools/release.py --bin <tested.bin>             # build/release-<ver>/
    python3 tools/release.py --bin <tested.bin> --expect-sha256 <hex>

`--local-saroo <dir>` instead copies YOUR OWN built BIN/CUE into a local
folder laid out like a SAROO SD card. That folder holds SEGA data. It is gated by the same confirmation and warning as tools/bundle.py
and is never part of the shareable package.
"""
import argparse
import ast
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]

# Mirrors the banned list in .github/workflows/ci.yml and .gitignore.
FORBIDDEN_SUFFIXES = {
    '.bin', '.cue', '.iso', '.chd', '.rom', '.img', '.mdf', '.mds', '.ccd', '.sub',
    '.nrg', '.smd', '.gen', '.sms', '.gg', '.mmd', '.nem', '.kos', '.raw', '.pcm',
    '.wav', '.mp3', '.ogg', '.flac', '.aiff', '.aif', '.adx', '.ppm', '.mp4', '.mov',
    '.state', '.smpc', '.elf', '.srm', '.bup',
}
FORBIDDEN_DIRS = ('assets', 'dist', 'build', 'cd', 'audio-tracks', '.deps', '.toolchain',
                  'roms', 'bios', 'extracted', 'hardware-results')
BIOS_NAME = re.compile(r'bios|sega_10[01]|mpr-1[78]\d{3}|sega1003|saturn_bios', re.I)
CD_SYNC = b'\x00' + b'\xff' * 10 + b'\x00'
SATURN_IP = b'SEGA SEGASATURN '

DOCS = ['README.md', 'CHANGELOG.md', 'LICENSE', 'THIRD-PARTY.md', 'JAPANESE-MUSIC.md']


class ForbiddenFile(Exception):
    """A file that must never go into the shareable package."""


def check_name(path):
    """Raise ForbiddenFile if the file name alone marks it as forbidden."""
    path = pathlib.PurePath(path)
    bad = {s.lower() for s in path.suffixes} & FORBIDDEN_SUFFIXES
    if bad:
        raise ForbiddenFile(f'{path}: forbidden file type {sorted(bad)[0]}')
    if BIOS_NAME.search(path.name):
        raise ForbiddenFile(f'{path}: looks like a BIOS file')


def check_allowed(path, root=ROOT):
    """Raise ForbiddenFile unless `path` is safe to share. Return the path."""
    path = pathlib.Path(path)
    check_name(path)
    resolved = path.resolve()
    try:
        rel = resolved.relative_to(pathlib.Path(root).resolve())
    except ValueError:
        rel = None
    if rel is not None and rel.parts and rel.parts[0] in FORBIDDEN_DIRS:
        raise ForbiddenFile(f'{path}: inside {rel.parts[0]}/ (private or generated data)')
    if path.is_file():
        with open(path, 'rb') as handle:
            head = handle.read(64)
        if head.startswith(CD_SYNC) or SATURN_IP in head or head.startswith(b'MComprHD'):
            raise ForbiddenFile(f'{path}: content is a disc image')
        if head[:4] in (b'RIFF', b'FORM') or head[:3] == b'ID3' or head[:4] == b'fLaC':
            raise ForbiddenFile(f'{path}: content is audio')
    return path


def scan_tree(folder):
    """Check every file under `folder`; raise on the first forbidden one."""
    for path in sorted(pathlib.Path(folder).rglob('*')):
        if path.is_file():
            # Staged files live under build/; judge them by name and content only.
            check_allowed(path, root=path.parent)


def read_ip(image_path):
    """Return the IP.BIN bytes from a 2048- or 2352-byte-sector image."""
    with open(image_path, 'rb') as handle:
        head = handle.read(256 + 16)
    if head[:16] == SATURN_IP:
        return head[:256]
    if head[16:32] == SATURN_IP:
        return head[16:16 + 256]
    raise SystemExit(f'{image_path}: no Saturn IP.BIN in the first sector')


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def makefile_value(key, root=ROOT):
    match = re.search(rf'^{key}:= *(\S+)', (root / 'Makefile').read_text(), re.M)
    if not match:
        raise SystemExit(f'{key} not found in Makefile')
    return match[1]


def release_notes(version, root=ROOT):
    for candidate in (root / f'RELEASE-NOTES-{version}.md',
                      root / 'docs' / 'archive' / f'RELEASE-NOTES-{version}.md'):
        if candidate.exists():
            return candidate
    raise SystemExit(f'RELEASE-NOTES-{version}.md not found')


def readme_sections(names, root=ROOT):
    """Return the named `## ` sections of README.md, in README order."""
    text = (root / 'README.md').read_text()
    parts = re.split(r'(?m)^(?=## )', text)
    keep = [p for p in parts if p.split('\n', 1)[0][3:].strip() in names]
    if len(keep) != len(names):
        raise SystemExit(f'README.md is missing one of {names}')
    return ''.join(keep).rstrip() + '\n'


def git_head(root=ROOT):
    try:
        out = subprocess.run(['git', '-C', str(root), 'rev-parse', 'HEAD'],
                             check=True, capture_output=True, text=True).stdout.strip()
        dirty = subprocess.run(['git', '-C', str(root), 'status', '--porcelain'],
                               check=True, capture_output=True, text=True).stdout.strip()
        return out, bool(dirty)
    except (OSError, subprocess.CalledProcessError):
        return None, None


def stage(src, dst, root=ROOT):
    check_allowed(src, root)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    return dst


def build_release(bin_path, out_dir, version=None, expect_sha=None, root=ROOT, make_zip=True):
    root = pathlib.Path(root)
    version = version or makefile_value('IP_VERSION', root)
    release_date = makefile_value('IP_RELEASE_DATE', root)
    bin_path = pathlib.Path(bin_path)
    bin_sha = sha256(bin_path)
    if expect_sha and bin_sha != expect_sha.lower():
        raise SystemExit(f'BIN SHA-256 {bin_sha} does not match --expect-sha256 {expect_sha}')
    ip = read_ip(bin_path)
    ip_version = ip[0x2A:0x30].decode('ascii', 'replace').strip()
    if ip_version != version:
        raise SystemExit(f'BIN IP.BIN version {ip_version} does not match release {version}')

    name = f'sonic-cd-saturn-{version}-source-release'
    out_dir = pathlib.Path(out_dir)
    pkg = out_dir / name
    if pkg.exists():
        shutil.rmtree(pkg)
    pkg.mkdir(parents=True)

    for doc in DOCS:
        stage(root / doc, pkg / doc, root)
    notes = release_notes(version, root)
    stage(notes, pkg / notes.name, root)

    building = pkg / 'BUILDING.md'
    building.write_text(
        f'# Building Sonic CD for Sega Saturn {version}\n\n'
        'Copied from README.md. JAPANESE-MUSIC.md covers the Japanese disc.\n\n'
        + readme_sections(['Requirements', 'Building'], root))
    verify = pkg / 'VERIFY.txt'
    verify.write_text(
        f'Sonic CD for Sega Saturn {version} ({release_date}): unofficial fan port\n'
        'Not affiliated with, endorsed by or sponsored by SEGA.\n\n'
        'This package contains no disc image, BIOS, audio or other SEGA data.\n'
        'Build the disc yourself from your own discs (see BUILDING.md), then\n'
        'check that your build matches the tested one:\n\n'
        f'  {bin_sha}  sonic-cd-saturn-prototype.bin\n'
        f'  size {bin_path.stat().st_size} bytes\n\n'
        '  macOS:  shasum -a 256 dist/sonic-cd-saturn-prototype.bin\n'
        '  Linux:  sha256sum dist/sonic-cd-saturn-prototype.bin\n\n'
        'A different hash means a different build. Report it with your hardware\n'
        'results; do not share the image.\n')
    (pkg / 'SHA256SUMS-TESTED-BIN.txt').write_text(f'{bin_sha}  sonic-cd-saturn-prototype.bin\n')

    commit, dirty = git_head(root)
    files = sorted(p for p in pkg.rglob('*') if p.is_file())
    manifest = {
        'name': 'Sonic CD for Sega Saturn (unofficial fan port)',
        'version': version,
        'release_date': release_date,
        'source_commit': commit,
        'source_tree_dirty': dirty,
        'contains_game_data': False,
        'tested_bin': {'file': 'sonic-cd-saturn-prototype.bin', 'sha256': bin_sha,
                       'bytes': bin_path.stat().st_size, 'included': False},
        'files': [{'path': str(p.relative_to(pkg)), 'bytes': p.stat().st_size,
                   'sha256': sha256(p)} for p in files],
    }
    (pkg / 'MANIFEST.json').write_text(json.dumps(manifest, indent=2) + '\n')
    scan_tree(pkg)

    archive = None
    if make_zip:
        archive = out_dir / f'{name}.zip'
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
            for path in sorted(p for p in pkg.rglob('*') if p.is_file()):
                info = zipfile.ZipInfo(f'{name}/{path.relative_to(pkg)}', (2026, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                zf.writestr(info, path.read_bytes())
        with zipfile.ZipFile(archive) as zf:
            assert zf.testzip() is None
            for member in zf.namelist():
                check_name(member)
    return pkg, archive


# ---------------------------------------------------------------- local SAROO

def bundle_warning():
    """Read FLAG, ENV_VAR, ENV_VALUE and WARNING from tools/bundle.py without running it."""
    tree = ast.parse((ROOT / 'tools' / 'bundle.py').read_text())
    values = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            key = node.targets[0].id
            if key in ('FLAG', 'ENV_VAR', 'ENV_VALUE', 'WARNING'):
                if isinstance(node.value, ast.Constant):
                    values[key] = node.value.value
                elif isinstance(node.value, ast.JoinedStr):
                    values[key] = ''.join(v.value for v in node.value.values if isinstance(v, ast.Constant))
    return values


def saroo_card_root(path):
    """Return the volume root if `path` is on a mounted SAROO card, else None."""
    parts = pathlib.Path(path).resolve().parts
    if len(parts) >= 3 and parts[1] == 'Volumes':
        volume = pathlib.Path(*parts[:3])
        if (volume / 'SAROO').is_dir():
            return volume
    return None


def local_saroo(dest, bin_path, cue_path=None, version=None):
    gate = bundle_warning()
    flag, env_var, env_value = gate['FLAG'], gate['ENV_VAR'], gate['ENV_VALUE']
    warning = gate['WARNING'].replace('tools/bundle.py makes a PRIVATE, LOCAL-ONLY bundle.',
                                      'tools/release.py --local-saroo makes a PRIVATE, LOCAL-ONLY folder.')
    print(warning, file=sys.stderr)
    if flag not in sys.argv[1:] and os.environ.get(env_var) != env_value:
        raise SystemExit(f'Refusing to run. Pass {flag} or set {env_var}={env_value} to confirm local use only.')
    card = saroo_card_root(dest)
    if card:
        raise SystemExit(f'Refusing to write to a mounted SAROO card ({card}). '
                         'Write to a local folder and copy it yourself.')
    version = version or makefile_value('IP_VERSION')
    bin_path = pathlib.Path(bin_path)
    cue_path = pathlib.Path(cue_path) if cue_path else bin_path.with_suffix('.cue')
    if not cue_path.exists():
        raise SystemExit(f'{cue_path} not found')
    if bin_path.name not in cue_path.read_text(errors='replace'):
        raise SystemExit(f'{cue_path.name} does not reference {bin_path.name}')
    dest = pathlib.Path(dest)
    game = dest / 'SAROO' / 'ISO' / f'Sonic CD Saturn {version}'
    game.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(bin_path, game / bin_path.name)
    shutil.copyfile(cue_path, game / cue_path.name)
    (dest / 'SAROO' / 'READ-ME-LOCAL-ONLY.txt').write_text(
        warning + '\n\n'
        f'ISO/Sonic CD Saturn {version}/ holds your BIN and CUE (sha256 {sha256(bin_path)}).\n')
    print(f'Wrote {dest}. Copy SAROO/ to your SD card yourself. Keep it local.', file=sys.stderr)
    return game


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--bin', required=True, help='the tested BIN (read for its hash and IP.BIN only)')
    parser.add_argument('--version', help='default: IP_VERSION in Makefile')
    parser.add_argument('--expect-sha256', help='fail unless the BIN has this SHA-256')
    parser.add_argument('--out', help='default: build/release-<version lowercase>/')
    parser.add_argument('--no-zip', action='store_true')
    parser.add_argument('--local-saroo', metavar='DIR', help='write your own BIN/CUE to a local SAROO folder')
    parser.add_argument('--cue', help='with --local-saroo: CUE path (default: BIN path with .cue)')
    parser.add_argument('--local-only-i-will-not-share', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.local_saroo:
        local_saroo(args.local_saroo, args.bin, args.cue, args.version)
        return 0
    version = args.version or makefile_value('IP_VERSION')
    out = pathlib.Path(args.out) if args.out else ROOT / 'build' / f'release-{version.lower()}'
    pkg, archive = build_release(args.bin, out, version, args.expect_sha256, make_zip=not args.no_zip)
    for path in sorted(p for p in pkg.rglob('*') if p.is_file()):
        print(f'{path.stat().st_size:>9}  {path.relative_to(out)}')
    if archive:
        print(f'{archive.stat().st_size:>9}  {archive.relative_to(out)}  sha256 {sha256(archive)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
