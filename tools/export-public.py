#!/usr/bin/env python3
"""Export HEAD as one clean public tree and audit it.

    python3 tools/export-public.py [--out DIR] [--message TEXT]

`git archive HEAD` puts tracked files into DIR, except those marked
`export-ignore` in .gitattributes (internal session and QA records). DIR defaults to
../sonic-cd-saturn-public-export next to this checkout and must not exist
or be empty. DIR gets `git init` and one commit with this repository's
user.name/user.email, dated like HEAD. No remote is added and nothing is
pushed.

The audit then checks the export and exits non-zero on any finding:
  retail hex   fromhex()/unhexlify() literals of 8+ bytes that occur in a
               file of the user's disc (build/retail/sonic.iso; required)
  private      paths under /Users/, /home/ or /Volumes/ (except the default
               SD-card mounts), the local account name, the name of the volume
               that holds this checkout, private LAN addresses, local
               hostnames, volume UUIDs, agent commit trailers, and every term
               in the private term list
  leak gate    the owner's outbound leak gate must pass every exported file

The private term list and the leak gate path are not in this repository. They
come from tools/export-public.private.json (gitignored):
    {"terms": ["..."], "leak_gate": "/path/to/leak-gate.py"}
The audit refuses to run without that file, so a missing list never passes.
  SEGA files   disc/audio/archive extensions, disc-image headers, and any
               file byte-identical to a file on the user's disc
  secrets      token and private-key patterns
"""
import argparse,getpass,hashlib,io,json,os,re,subprocess,sys,tarfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from extract_mmd import disc_files  # noqa: E402

HEX=re.compile(r"""(?:fromhex|unhexlify)\(\s*[rb]?(['"])([0-9A-Fa-f \n]{16,})\1""")
# /Volumes/Untitled and /Volumes/NO NAME are macOS's default SD-card mounts (SAROO steps).
PRIVATE=re.compile(r'/Users/[A-Za-z0-9._-]+|/Volumes/(?!Untitled\b|NO NAME\b)[A-Za-z0-9._-]+|/home/[a-z][a-z0-9_-]+/')
NETWORK=re.compile(r'\b(?:10\.\d{1,3}|192\.168|172\.(?:1[6-9]|2\d|3[01]))\.\d{1,3}\.\d{1,3}\b|'
                   r'\b[A-Za-z0-9-]+\.(?:local|lan|home\.arpa)\b|'
                   r'\b[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}\b|'
                   r'(?im:^\s*(?:co-authored-by|claude-session):)')
LOCAL=ROOT/'tools/export-public.private.json'
SECRETS=re.compile(r'ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|sk-ant-[A-Za-z0-9_-]{20,}|'
                   r'AKIA[0-9A-Z]{16}|xox[abprs]-[A-Za-z0-9-]{10,}|-----BEGIN [A-Z ]*PRIVATE KEY-----|'
                   r'(?i:api[_-]?key|secret|token|password)\s*[=:]\s*[\'"][A-Za-z0-9_\-]{16,}[\'"]')
SEGA_EXT={'.bin','.iso','.cue','.chd','.mmd','.stm','.wav','.pcm','.raw','.mds','.mdf','.ccd','.img','.scsp',
          '.zip','.7z','.rar','.gz','.bz2','.xz','.tar'}
# Disc and audio container magic at offset 0 (or the ISO 9660 descriptor at 0x8001).
MAGIC=(b'SEGADISCSYSTEM',b'SEGA SEGASATURN',b'RIFF',b'MComprHD',b'PK\x03\x04',b'7z\xbc\xaf')
TEXT_OK=(b'#!',)


def git(*args,cwd=ROOT,env=None):
    return subprocess.run(['git',*args],cwd=cwd,env=env,check=True,capture_output=True,text=True).stdout.strip()


def export(out,message):
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f'{out} exists and is not empty; remove it first')
    out.mkdir(parents=True,exist_ok=True)
    data=subprocess.run(['git','archive','--format=tar','HEAD'],cwd=ROOT,check=True,capture_output=True).stdout
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        tar.extractall(out,filter='tar')
    name,email=git('config','user.name'),git('config','user.email')
    when=git('log','-1','--format=%cI')
    env={**os.environ,'GIT_AUTHOR_NAME':name,'GIT_AUTHOR_EMAIL':email,'GIT_COMMITTER_NAME':name,
         'GIT_COMMITTER_EMAIL':email,'GIT_AUTHOR_DATE':when,'GIT_COMMITTER_DATE':when}
    git('init','-q','-b','main',cwd=out)
    git('config','user.name',name,cwd=out);git('config','user.email',email,cwd=out)
    # -f: a tracked file that .gitignore matches still belongs in the export.
    git('add','-A','-f',cwd=out,env=env)
    git('commit','-q','--no-verify','-m',message,cwd=out,env=env)
    return git('rev-parse','HEAD',cwd=out),git('rev-parse','HEAD'),name,email


def audit(out):
    iso=ROOT/'build/retail/sonic.iso'
    if not iso.exists():raise SystemExit(f'{iso} is missing; the retail-code check needs the user\'s disc')
    disc=disc_files(iso.read_bytes())
    blob=b'\0'.join(disc.values())
    disc_sha={hashlib.sha256(d).hexdigest():n for n,d in disc.items()}
    account=getpass.getuser()
    if not LOCAL.exists():raise SystemExit(f'{LOCAL} is missing; the private term list and leak gate are required')
    local=json.loads(LOCAL.read_text())
    terms=[t for t in local['terms'] if t.strip()]
    gate=Path(local['leak_gate']).expanduser()
    if not terms or not gate.is_file():raise SystemExit(f'{LOCAL}: needs a non-empty "terms" list and an existing "leak_gate"')
    volume=ROOT.parts[2] if ROOT.parts[1:2]==('Volumes',) and len(ROOT.parts)>3 else None
    if volume:terms.append(volume)
    named=re.compile('|'.join(re.escape(t) for t in terms),re.I)
    files=sorted(str(p.relative_to(out)) for p in out.rglob('*') if '.git' not in p.relative_to(out).parts and (p.is_symlink() or p.is_file()))
    findings={'retail hex':[],'private':[],'SEGA files':[],'secrets':[],'leak gate':[]}
    hex_total=0
    for rel in files:
        path=out/rel
        if path.is_symlink() or not path.is_file():continue
        data=path.read_bytes()
        if Path(rel).suffix.lower() in SEGA_EXT:findings['SEGA files'].append(f'{rel}: extension')
        if data.startswith(MAGIC) or data[0x8001:0x8006]==b'CD001':findings['SEGA files'].append(f'{rel}: disc or archive header')
        if hashlib.sha256(data).hexdigest() in disc_sha:findings['SEGA files'].append(f'{rel}: identical to {disc_sha[hashlib.sha256(data).hexdigest()]}')
        if b'\0' in data and not data.startswith(TEXT_OK):continue
        text=data.decode('utf-8','replace')
        line=lambda m:text.count('\n',0,m.start())+1
        for m in HEX.finditer(text):
            hex_total+=1
            raw=bytes.fromhex(re.sub(r'\s','',m.group(2)))
            if raw in blob:findings['retail hex'].append(f'{rel}:{line(m)}: {len(raw)} bytes on the disc')
        for m in PRIVATE.finditer(text):findings['private'].append(f'{rel}:{line(m)}: {m.group(0)}')
        if re.search(rf'\b{re.escape(account)}\b',text):findings['private'].append(f'{rel}: account name {account}')
        for m in NETWORK.finditer(text):findings['private'].append(f'{rel}:{line(m)}: {m.group(0).strip()}')
        for m in named.finditer(text):findings['private'].append(f'{rel}:{line(m)}: private term')
        for m in SECRETS.finditer(text):findings['secrets'].append(f'{rel}:{line(m)}: {m.group(0)[:12]}...')
    if subprocess.run([sys.executable,str(gate),'--check-pin'],capture_output=True).returncode:
        findings['leak gate'].append('--check-pin failed; restore the pin before publishing')
    regular=[str(out/rel) for rel in files if (out/rel).is_file() and not (out/rel).is_symlink()]
    for i in range(0,len(regular),200):
        run=subprocess.run([sys.executable,str(gate),'--profile','public','--quiet',*regular[i:i+200]],capture_output=True,text=True)
        if run.returncode:findings['leak gate'].append(f'exit {run.returncode}: '+(run.stdout+run.stderr).strip()[-300:])
    message=git('log','-1','--format=%an%n%ae%n%B',cwd=out)
    if NETWORK.search(message) or named.search(message):findings['private'].append('commit message or author: private term')
    return files,hex_total,findings


def ip_version():
    """IP_VERSION from the Makefile, e.g. V0.080."""
    m=re.search(r'^IP_VERSION\s*:?=\s*(\S+)',(ROOT/'Makefile').read_text(),re.M)
    if not m:raise SystemExit('Makefile: no IP_VERSION line')
    return m.group(1)


def main():
    ap=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out',type=Path,default=ROOT.parent/'sonic-cd-saturn-public-export')
    ap.add_argument('--message',default=f'Sonic CD Saturn {ip_version()} source',
                    help='commit message (default: %(default)s, from IP_VERSION in the Makefile)')
    args=ap.parse_args()
    commit,source,name,email=export(args.out.resolve(),args.message)
    files,hex_total,findings=audit(args.out.resolve())
    committed=git('ls-files',cwd=args.out.resolve()).splitlines()
    source_files=git('ls-files').splitlines()
    ignored={l.split(': ')[0] for l in subprocess.run(['git','check-attr','--stdin','export-ignore'],cwd=ROOT,input='\n'.join(source_files),
             capture_output=True,text=True,check=True).stdout.splitlines() if l.endswith(': set')}
    source_files=[f for f in source_files if f not in ignored and not any(f.startswith(d+'/') for d in ignored)]
    if sorted(committed)!=sorted(files) or sorted(committed)!=sorted(source_files):
        findings['export']=sorted(set(committed)^set(files)|set(committed)^set(source_files))
    print(f'export: {args.out.resolve()}  commit {commit[:12]} from {source[:12]}  author {name} <{email}>')
    print(f'files: {len(files)}; fromhex literals: {hex_total} (none may occur on the disc); remotes: '
          f'{len(git("remote",cwd=args.out.resolve()).split())}')
    for kind,items in findings.items():
        print(f'{kind}: {len(items)}')
        for item in items[:20]:print('  '+item)
    bad=sum(map(len,findings.values()))
    print('PASS: public export audit clean' if not bad else f'FAIL: public export audit: {bad} findings')
    sys.exit(1 if bad else 0)


if __name__=='__main__':main()
