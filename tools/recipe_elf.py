"""ELF32 source-provenance metadata for recipe builders and independent audits."""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess


@dataclass(frozen=True)
class Section:
    index: int
    name: str
    kind: int
    flags: int
    address: int
    offset: int
    size: int
    link: int
    info: int
    alignment: int
    entry_size: int


class Elf:
    def __init__(self, path, data=None):
        self.path = Path(path)
        self.data = self.path.read_bytes() if data is None else data
        if self.data[:6] not in (b'\x7fELF\x01\x01', b'\x7fELF\x01\x02'):
            raise ValueError('Expected ELF32')
        self.endian = '>' if self.data[5] == 2 else '<'
        h = struct.unpack_from(self.endian+'16sHHIIIIIHHHHHH', self.data)
        raw = [struct.unpack_from(self.endian+'10I', self.data, h[6]+i*h[11]) for i in range(h[12])]
        names = self.data[raw[h[13]][4]:raw[h[13]][4]+raw[h[13]][5]]
        self.sections = [Section(i, self.string(names, r[0]), *r[1:]) for i, r in enumerate(raw)]
        self.symbols = []
        for section in self.sections:
            if section.kind != 2:
                continue
            strings = self.content(self.sections[section.link])
            for at in range(section.offset, section.offset+section.size, section.entry_size):
                n, value, size, info, other, si = struct.unpack_from(self.endian+'IIIBBH', self.data, at)
                self.symbols.append(dict(name=self.string(strings,n),value=value,bytes=size,type=info&15,
                                         binding=info>>4,section=si))
        self.segments = [struct.unpack_from(self.endian+'8I', self.data,h[5]+i*h[9]) for i in range(h[10])]
        self.sha256 = hashlib.sha256(self.data).hexdigest()

    @staticmethod
    def string(data, offset):
        end = data.find(b'\0',offset)
        if end < 0:
            raise ValueError('Unterminated ELF string')
        return data[offset:end].decode('utf8','replace')

    def content(self, section):
        return self.data[section.offset:section.offset+section.size]

    def load_address(self, section):
        for kind, offset, vma, lma, files, memory, flags, alignment in self.segments:
            if kind == 1 and offset <= section.offset and section.offset+section.size <= offset+files:
                return lma+section.offset-offset
        raise ValueError('No load segment for '+section.name)


def public_source_path(source, root):
    path = Path(source)
    if path.is_absolute():
        try:
            return path.relative_to(root).as_posix()
        except ValueError:
            return None
    if '..' in path.parts:
        return None
    return path.as_posix()


def initializer_evidence(root, symbols,work):
    """Return declaration candidates, not ordinary assignment sites.

    A symbol can have multiple local declarations with the same C name. The
    builder must resolve those by initializer/serialized bytes. An ambiguous
    generated candidate must never be silently classified as a literal.
    """
    wanted = {name for s in symbols if s['type'] == 1 for name in source_names(s['name'])}
    evidence = {}
    declaration = re.compile(r'\b([A-Za-z_]\w*)\s*(?:\[[^\]\n]*\]\s*)*(?:\)\s*\([^;={}]*\))?\s*=(?!=)')
    for unit in sorted((root/'build/saturn').glob('*.i')):
        names=set()
        translation_unit=None
        for tag in ('@src@','@build@'):
            if tag in unit.name:translation_unit=tag.strip('@')+'/'+unit.name.split(tag,1)[1].replace('@','/').removesuffix('.i')+'.c'
        for line in unit.open(errors='replace'):
            if '='not in line:continue
            for match in declaration.finditer(line):
                name = match[1]
                if name in wanted:names.add(name)
        for name in sorted(names):
            for declaration_row in compiler_declarations(unit,name,work):
                if not declaration_row['initialized'] or not declaration_row['static_storage']:continue
                row=dict(declaration_row,translation_unit=translation_unit)
                if row not in evidence.setdefault(name,[]):evidence[name].append(row)
    return evidence


def generated_input(source, root):
    # Permission for compiled CC0 functions does not admit game data tables.
    if source.startswith('build/probe-source/') or source=='src/objects_mm_remaining.inc':
        return True
    if source.startswith('assets/generated/'):
        return True
    if re.fullmatch(r'src/background_r[3-8]_(?:tables|palette)\.inc',source):
        return True
    if source in ('src/scroll_limits.h','src/stage_zone_packs.h'):
        return True
    path = root/source
    if path.is_file() and path.suffix in ('.inc','.h','.c'):
        with path.open(errors='replace') as stream:
            prefix = stream.read(512)
        # DSP program words are generated from project code, without retail inputs.
        if source.startswith('src/cdda_provider/'):
            return False
        if re.search(r'Generated by tools/|generated from.*(?:retail|scddisasm)',prefix,re.I):
            return True
    return False


def generated_evidence(evidence,root):
    return any(generated_input(source,root)for source in [evidence['source'],*evidence.get('initializer_sources',[])])


def source_names(symbol):
    name=symbol[1:] if symbol.startswith('_') else symbol
    name=name.split('.')[0]
    # credits_sections.py renames symbols after preprocessing/compilation.
    return [name,name.removeprefix('fe_cr_')] if name.startswith('fe_cr_') else [name]


def source_aliases(name,aliases):
    result=set();pending=[name]
    while pending:
        value=pending.pop()
        if value in result:continue
        result.add(value);pending.extend(aliases.get(value,[]))
    return result


def compiler_declarations(unit,name,work):
    """Ask Clang for declaration metadata; discard initializer values immediately.

    This handles multiline/multiple declarators and function-pointer arrays.
    The browser still reads the converter source, never this compiler AST.
    """
    unit_hash=hashlib.sha256(unit.read_bytes()).hexdigest()
    cache=work/(unit_hash+'-'+name+'.declarations-v7.json')
    if cache.exists():return json.loads(cache.read_text())
    result=subprocess.run(['clang','-target','wasm32-unknown-unknown','-x','c','-fsyntax-only',
        '-Wno-everything','-Xclang','-ast-dump=json','-Xclang','-ast-dump-filter='+name,str(syntax_unit(unit,work))],capture_output=True,text=True)
    if result.returncode:
        cache.with_suffix('.errors').write_text(result.stderr)
        raise ValueError('Clang declaration extraction failed: '+cache.name)
    declarations=[]
    def collect(node):
        if node.get('kind')=='VarDecl' and node.get('name')==name:declarations.append(node)
        return node
    decoder=json.JSONDecoder(object_hook=collect);at=0;rows=[]
    while at<len(result.stdout):
        if result.stdout[at].isspace():at+=1;continue
        node,end=decoder.raw_decode(result.stdout,at);at=end
    # A filter also matches enclosing function names. Clang then emits the
    # variable inside that function's AST, not as a separate top-level dump.
    for node in declarations:
        loc=node.get('loc',{})
        if 'offset'not in loc:continue
        prefix=unit.read_bytes()[:loc['offset']].decode()
        markers=list(re.finditer(r'(?m)^#\s+(\d+)\s+"([^"]+)"[^\n]*\n',prefix))
        if not markers:continue
        marker=markers[-1]
        source=public_source_path(marker[2],unit.resolve().parents[2])
        if source is None:continue
        source_line=int(marker[1])+prefix[marker.end():].count('\n')
        lexical=re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'','',prefix)
        file_scope=lexical.count('{')==lexical.count('}')
        initializer_sources=set()
        for child in node.get('inner',[]):
            if not ('Expr'in child['kind'] or child['kind'].endswith('Literal')):continue
            begin,end=child['range']['begin'],child['range']['end']
            if 'offset'not in begin or 'offset'not in end:continue
            initial=unit.read_bytes()[:begin['offset']].decode()
            initial_markers=list(re.finditer(r'(?m)^#\s+(\d+)\s+"([^"]+)"[^\n]*\n',initial))
            paths=[initial_markers[-1][2]]if initial_markers else []
            body=unit.read_bytes()[begin['offset']:end['offset']+end.get('tokLen',1)].decode()
            paths.extend(re.findall(r'(?m)^#\s+\d+\s+"([^"]+)"',body))
            initializer_sources.update(p for p in (public_source_path(s,unit.resolve().parents[2])for s in paths)if p)
        rows.append(dict(source=source,line=source_line,variable=name,
            ctype=node['type']['qualType'],translation_unit_sha256=unit_hash,
            compiler_declaration=True,initialized='init'in node,offset=loc['offset'],
            static_storage=node.get('storageClass')=='static' or (file_scope and node.get('storageClass')!='extern'),
            initializer_sources=sorted(initializer_sources)))
    cache.write_text(json.dumps(rows)+'\n')
    return rows


def syntax_unit(unit,work):
    """Neutralize SH inline assembly for host-only C declaration/layout queries.

    Neither code nor initializer expressions are compiled into the recipe.
    Preserve offsets/newlines so compiler source locations remain valid.
    """
    text=unit.read_text();key=hashlib.sha256(text.encode()).hexdigest()
    path=work/(key+'.syntax-v4.i')
    if path.exists():return path
    pattern=re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|(?P<query>\b(?:__asm__|__asm|asm|_Static_assert)\s*(?:(?:volatile|__volatile__)\s*)?\()')
    changes=[]
    for match in pattern.finditer(text):
        if match['query']is None:continue
        at=match.end();depth=1;quote=None;escape=False
        while depth and at<len(text):
            char=text[at];at+=1
            if escape:escape=False
            elif quote:
                if char=='\\':escape=True
                elif char==quote:quote=None
            elif char in "\"'":quote=char
            elif char=='(':depth+=1
            elif char==')':depth-=1
        if depth:raise ValueError('Unbalanced compiler assembly expression')
        old=text[match.start():at];replacement=list(''.join('\n'if c=='\n'else' 'for c in old))
        protected=set()
        for marker in re.finditer(r'(?m)^[ \t]*#\s*\d+[^\n]*',old):
            replacement[marker.start():marker.end()]=old[marker.start():marker.end()]
            protected.update(range(marker.start(),marker.end()))
        tokens=('_Static_assert','(','1',',','""',')') if old.startswith('_Static_assert') else ('asm','(','""',')')
        cursor=0
        for token in tokens:
            while cursor+len(token)<=len(old) and any(i in protected or old[i]=='\n'for i in range(cursor,cursor+len(token))):cursor+=1
            if cursor+len(token)>len(old):raise ValueError('No space for neutral compiler expression')
            replacement[cursor:cursor+len(token)]=token;cursor+=len(token)
        changes.append((match.start(),at,''.join(replacement)))
    for start,end,replacement in reversed(changes):text=text[:start]+replacement+text[end:]
    # SH-only ABI assertions cannot validate a wasm layout query. Every
    # layout actually used is instead checked against the accepted SH symbol's
    # size and complete serialized bytes by recipe_tables.py.
    # Yaul's GCC headers omit the semicolon after three anonymous unions.
    # Consume one indentation character to insert it without shifting offsets.
    text=re.sub(r'(?m)([ \t]+)\}(?=\n\}\s*__attribute__\s*\(\(__may_alias__\)\))',
                lambda m:m[1][:-1]+'};',text)
    if len(text.encode())!=len(unit.read_bytes()) or text.count('\n')!=unit.read_text().count('\n'):
        raise ValueError('Metadata normalization changed compiler locations')
    if re.findall(r'(?m)^#\s+\d+[^\n]*',text)!=re.findall(r'(?m)^#\s+\d+[^\n]*',unit.read_text()):
        raise ValueError('Metadata normalization changed source markers')
    path.write_text(text)
    return path


def symbol_provenance(root, symbol, evidence):
    if symbol['type'] == 2:
        return dict(kind='literal',owner='compiled-function-and-pools',evidence=[])
    candidates = [e for name in source_names(symbol['name']) for e in evidence.get(name,[])]
    candidates=list({(e['source'],e['line'],e.get('variable')):e for e in candidates}.values())
    generated = [e for e in candidates if generated_evidence(e,root)]
    if generated:
        return dict(kind='derive',owner='generated-initializer',evidence=generated+[e for e in candidates if e not in generated])
    project = [e for e in candidates if e['source'].startswith('src/')]
    if project:
        return dict(kind='derive',owner='project-source-initializer',evidence=project)
    return dict(kind='unresolved',owner='object-attribution-required',evidence=candidates)
