"""Owner-approved program/data classification from the linked ELF and .i markers.

The output contains addresses, hashes and source evidence, never symbol payloads.
Any remaining unclassified range blocks a distributable recipe.
"""
import hashlib
import ast
import json
from pathlib import Path
import re
import struct
import subprocess
from recipe_elf import Elf, initializer_evidence, symbol_provenance, public_source_path, generated_input, generated_evidence, source_names, source_aliases, compiler_declarations
from recipe_values import c_string

FORBIDDEN_LITERAL_OWNERS=frozenset(('CC0-compiled-data','CC0-adapted-program-data','compiled-object-data','project-source-initializer','dependency-source-initializer'))
PROGRAM_LITERAL_OWNERS=frozenset(('compiled-function-and-pools','source-string','dependency-program-string','compiled-control-table',
    'compiled-function-constant','PoneSound-MIT-program','linker-zero-fill'))


def literal_owner_totals(construction):
    """Fail closed on legacy data permissions and absent source evidence."""
    totals={}
    for row in construction['literal_ranges']:
        evidence=row['evidence']
        if isinstance(evidence,int):evidence=construction['literal_evidence'][evidence]
        owner=row['owner']
        if owner in FORBIDDEN_LITERAL_OWNERS:raise ValueError('Forbidden literal owner: '+owner)
        if owner=='program':
            symbols=evidence['provenance']
            for symbol in symbols:
                if symbol['owner'] in FORBIDDEN_LITERAL_OWNERS:raise ValueError('Forbidden literal owner: '+symbol['owner'])
            if len(symbols)!=1:raise ValueError('Literal range must have one source ownership proof')
            symbol=symbols[0];owner=symbol['owner']
            if owner not in PROGRAM_LITERAL_OWNERS:raise ValueError('Unapproved program literal owner: '+owner)
            if not symbol['evidence'] or any(not e.get('source') for e in symbol['evidence']):
                raise ValueError('Literal lacks source-file evidence: '+symbol['symbol'])
            if owner=='project-source-initializer' and any(generated_evidence(e,Path(__file__).resolve().parents[1])for e in symbol['evidence']):
                raise ValueError('Generated initializer cannot be a project literal')
        elif not evidence.get('source'):
            raise ValueError('Literal lacks source-file evidence: '+owner)
        totals[owner]=totals.get(owner,0)+row['bytes']
    return totals


def intervals(mask):
    if not mask:
        return []
    rows=[]
    start=0
    for end in range(1,len(mask)+1):
        if end==len(mask) or mask[end]!=mask[start]:
            rows.append(dict(offset=start,bytes=end-start,kind={0:'unresolved',1:'literal',2:'derive'}[mask[start]]))
            start=end
    return rows


def archive_members(path):
    data=path.read_bytes()
    if not data.startswith(b'!<arch>\n'):raise ValueError('Invalid program archive')
    at=8;names=b''
    while at<len(data):
        header=data[at:at+60];length=int(header[48:58]);name=header[:16].decode().strip()
        body=data[at+60:at+60+length];at+=60+length+(length%2)
        if name=='//':names=body;continue
        if name=='/':continue
        if name.startswith('/')and name[1:].isdigit():name=names[int(name[1:]):].split(b'/\n',1)[0].decode()
        else:name=name.rstrip('/')
        yield name,body


class SourceIndex:
    """Resolve object hints to source declarations, never to ownership alone."""
    def __init__(self,root,work):
        self.root=root;self.work=work;self.files={};self.by_stem={};self.functions={};self.aliases={};self.archived={};self.hashes={}
        self.units=list((root/'build/saturn').glob('*.i'))
        for directory in ('src','.deps/libyaul/libyaul','build/probe-source','build/feedback'):
            for path in sorted((root/directory).rglob('*')):
                if not path.is_file() or path.suffix not in ('.c','.h','.inc','.S','.s','.x'):continue
                source=path.relative_to(root).as_posix();text=path.read_text(errors='replace')
                self.files[source]=text
                self.by_stem.setdefault(path.stem,[]).append(source)
                clean=re.sub(r'__attribute__\s*\(\((?:[^()]|\([^()]*\))*\)\)',lambda m:' '*len(m[0]),text)
                for m in re.finditer(r'\b([A-Za-z_]\w*)\s*\((?:[^(){};]|\([^(){};]*\))*\)\s*\{',clean):
                    self.functions.setdefault(m[1],[]).append((source,text.count('\n',0,m.start())+1))
                for a,b in re.findall(r'^\s*#define\s+(\w+)\s+(\w+)\s*$',text,re.M):self.aliases.setdefault(b,[]).append(a)
        gcc_sources={}
        for name in ('libgcc2.c','config/sh/lib1funcs.S'):
            source='.deps/gcc-13.4.0/libgcc/'+name
            if (root/source).is_file():
                self.files[source]=(root/source).read_text();gcc_sources[Path(name).name]=source
        for archive in (root/'.toolchain/sh-elf/lib/libyaul.a',root/'.toolchain/lib/gcc/sh-elf/13.4.0/libgcc.a'):
            archive_hash=hashlib.sha256(archive.read_bytes()).hexdigest()
            for member,body in archive_members(archive):
                if not body.startswith(b'\x7fELF'):continue
                obj=Elf(member,body)
                files=[s['name']for s in obj.symbols if s['type']==4 and s['name']]
                proofs=[]
                for filename in files:
                    local=self.by_stem.get(Path(filename).stem,[])
                    if local:proofs.extend(self.row(s,1,attribution='archive compiler source file')for s in local)
                    elif archive.name=='libgcc.a':
                        source=gcc_sources.get(Path(filename).name)
                        if source:proofs.append(self.row(source,1,attribution='ELF STT_FILE',
                            archive='libgcc.a',archive_sha256=archive_hash,object=member,object_sha256=hashlib.sha256(body).hexdigest()))
                if not files and archive.name=='libgcc.a' and 'lib1funcs.S'in gcc_sources:
                    proofs.append(self.row(gcc_sources['lib1funcs.S'],1,attribution='GCC SH assembly build source',
                        archive='libgcc.a',archive_sha256=archive_hash,object=member,object_sha256=hashlib.sha256(body).hexdigest()))
                for symbol in obj.symbols:
                    if symbol['type']in (0,1,2) and symbol['section'] and symbol['name']:
                        self.archived.setdefault(symbol['name'].split('.')[0],[]).extend(proofs)

    def row(self,source,line,**extra):
        if source not in self.hashes:self.hashes[source]=hashlib.sha256((self.root/source).read_bytes()).hexdigest()
        return dict(source=source,line=line,source_sha256=self.hashes[source],**extra)

    def function(self,symbol,origins=()):
        result=[]
        for name in source_names(symbol):
            for candidate in source_aliases(name,self.aliases):
                result.extend(self.row(s,n) for s,n in self.functions.get(candidate,[]))
        if not result:
            for origin in origins:
                source=origin['source'].removesuffix('.o')+'.c'
                if source in self.files:result.append(self.row(source,1,attribution='compiled translation unit'))
        if not result:result.extend(self.archived.get(symbol.split('.')[0],[]))
        if not result:
            for unit in self.units:
                text=unit.read_text()
                clean=re.sub(r'__attribute__\s*\(\((?:[^()]|\([^()]*\))*\)\)',lambda m:' '*len(m[0]),text)
                for name in source_names(symbol):
                    for match in re.finditer(r'\b'+re.escape(name)+r'\s*\([^;{}]*\)\s*\{',clean):
                        markers=list(re.finditer(r'(?m)^#\s+(\d+)\s+"([^"]+)"[^\n]*\n',text[:match.start()]))
                        if not markers:continue
                        marker=markers[-1];source=public_source_path(marker[2],self.root)
                        if source is None:continue
                        line=int(marker[1])+text[marker.end():match.start()].count('\n')
                        result.append(dict(source=source,line=line,translation_unit_sha256=hashlib.sha256(unit.read_bytes()).hexdigest()))
        return list({json_key(row):row for row in result}.values())

    def resolve(self,symbol,origins,zero=False):
        names=source_names(symbol['name']);result=[]
        for origin in origins:
            hint=origin['source']
            if hint.startswith(('src/','build/')):sources=[hint.removesuffix('.o')+'.c']
            else:sources=self.by_stem.get(hint.split(':')[-1].removesuffix('.o'),[])
            if symbol['name'].startswith('_CSWTCH.'):
                for source in sources:
                    for n,line in enumerate(self.files.get(source,'').splitlines(),1):
                        if re.search(r'\bswitch\s*\(|\bif\s*\(',line):result.append(self.row(source,n,compiler='GCC control conversion'))
                continue
            if hint.startswith(('src/','build/')):
                for unit in self.units:
                    if not any(unit.name.endswith(s.replace('/','@').removesuffix('.c')+'.i')for s in sources):continue
                    for name in names:
                        result.extend(row for row in compiler_declarations(unit,name,self.work) if row['static_storage'] and (row['initialized'] or zero))
                continue
            # SDK declarations can live in an included source/header. A mere
            # occurrence at a use site does not certify an initializer.
            candidates=sources if hint.startswith(('src/','build/')) else [p for p in self.files if p.startswith('.deps/libyaul/')]
            for source in candidates:
                for n,line in enumerate(self.files.get(source,'').splitlines(),1):
                    for name in names:
                        if re.search(r'\bMEMB\(\s*'+re.escape(name)+r'\s*,',line):
                            result.append(self.row(source,n,variable=name,initialization='MEMB declaration macro'))
                            continue
                        cleaned=re.sub(r'__\w+\s*\([^()]*\)|\b__(?:uncached|used|unused|packed)\b','',line)
                        match=re.search(r'\b'+re.escape(name)+r'\s*(?:\[[^\]]*\]\s*)*(?:\)\s*\([^;={}]*\))?\s*(=|;)',cleaned)
                        if match is None or (match[1]==';' and not zero):continue
                        prefix=cleaned[:match.start()].strip()
                        if not prefix or re.search(r'\b(?:return|if|while)\b|->',prefix):continue
                        if not (re.match(r'(?:static|const|volatile|extern|unsigned|signed|struct|char|int|short|long|\w+_t)\b',prefix) or prefix=='}'):continue
                        result.append(self.row(source,n,variable=name,initialization='implicit zero' if match[1]==';' else 'source initializer'))
        if not result and symbol['name']=='___clz_tab':
            for proof in self.archived.get(symbol['name'],[]):
                match=re.search(r'\b__clz_tab\s*\[',self.files[proof['source']])
                if match:result.append(dict(proof,line=self.files[proof['source']].count('\n',0,match.start())+1,
                    variable='__clz_tab',initialization='source initializer'))
        return list({json_key(row):row for row in result}.values())


def json_key(row):
    return json.dumps(row,sort_keys=True,separators=(',',':'))


def complete(root,provenance,tables):
    """Add certified generated strings and compiler constant references.

    Named generated data always wins. Unnamed constants require a DIR32
    reference in an attributed function; merely being printable is not proof.
    """
    elf=Elf(root/'build/saturn/sonic-cd-saturn-prototype.elf')
    if elf.sha256!=provenance['elf_sha256']or elf.sha256!=tables['elf_sha256']:
        raise ValueError('Different accepted ELF inputs')
    references=[]
    for reloc in elf.sections:
        if reloc.kind!=4:continue
        section=elf.sections[reloc.info]
        if not section.flags&4:continue
        for at in range(reloc.offset,reloc.offset+reloc.size,reloc.entry_size):
            address,info,addend=struct.unpack_from(elf.endian+'IIi',elf.data,at)
            if info&255!=1:continue
            target=int.from_bytes(elf.data[section.offset+address-section.address:section.offset+address-section.address+4],'big')
            functions=[s['name']for s in elf.symbols if s['type']==2 and s['section']==reloc.info
                       and s['value']<=address<s['value']+s['bytes']]
            if functions:references.append(dict(address=address,target=target,functions=functions,relocation='R_SH_DIR32'))
    for file,out in provenance['programs'].items():
        image=(root/file).read_bytes();mask=bytearray(out['bytes'])
        for row in out['ranges']:
            mask[row['offset']:row['offset']+row['bytes']]=bytes([{'unresolved':0,'literal':1,'derive':2}[row['kind']]])*row['bytes']
        for row in tables['strings']:
            if row['file']!=file:continue
            mask[row['offset']:row['offset']+row['bytes']]=bytes([2])*row['bytes']
            evidence=dict(source=row['source'],sha256=row['sha256'])
            if row['codec']=='source-text-string':evidence.update(source_offset=row['source_offset'],source_length=row['source_length'],mode=row['mode'])
            else:evidence.update(variable=row['variable'],occurrence=row['occurrence'],leaf=row['leaf'])
            out['symbols'].append(dict(symbol='<source-derived-string>',offset=row['offset'],bytes=row['bytes'],
                section='.rodata',kind='derive',owner='source-derived-string',evidence=[evidence]))
        for row in intervals(mask):
            if row['kind']!='unresolved' or not any(image[row['offset']:row['offset']+row['bytes']]):continue
            if row['bytes']>16:continue
            start=out['base']+row['offset'];end=start+row['bytes']
            refs=[r for r in references if start<=r['target']<end]
            if not refs:continue
            sources=[e for ref in refs for function in ref['functions'] for program in provenance['programs'].values()
                for symbol in program['symbols'] if symbol['symbol']==function and symbol['owner']=='compiled-function-and-pools'
                for e in symbol['evidence']]
            mask[row['offset']:row['offset']+row['bytes']]=bytes([1])*row['bytes']
            out['symbols'].append(dict(symbol='<function-constant>',offset=row['offset'],bytes=row['bytes'],
                section='.rodata',kind='literal',owner='compiled-function-constant',evidence=[dict(e,references=refs)for e in sources]))
        for row in intervals(mask):
            if row['kind']!='unresolved':continue
            start,end=row['offset'],row['offset']+row['bytes']
            if any(image[start:end]):continue
            neighbors={mask[i]for i in (start-1,end)if 0<=i<len(mask)and mask[i]}
            if neighbors:mask[start:end]=bytes([2 if 2 in neighbors else 1])*(end-start)
        out['ranges']=intervals(mask)
        out['unresolved_bytes']=sum(r['bytes']for r in out['ranges']if r['kind']=='unresolved')
    return provenance


def classify(root,work=None):
    elf=Elf(root/'build/saturn/sonic-cd-saturn-prototype.elf')
    if work is None:raise ValueError('A private declaration-cache directory is required')
    work.mkdir(parents=True,exist_ok=True)
    evidence=initializer_evidence(root,elf.symbols,work)
    objects={};objects_by_name={};objects_exact={}
    inputs=list((root/'build/saturn').glob('*.o'))+[root/'.toolchain/sh-elf/lib/libyaul.a',root/'.toolchain/lib/gcc/sh-elf/13.4.0/libgcc.a']
    listing=subprocess.check_output([str(root/'.toolchain/bin/sh-elf-nm'),'-A','-S',*map(str,inputs)],text=True,stderr=subprocess.DEVNULL)
    for line in listing.splitlines():
        fields=line.split()
        if len(fields)!=4:continue
        try:size=int(fields[1],16)
        except ValueError:continue
        location=fields[0].rsplit(':',1)[0]
        if '.a:'in location:
            archive,member=location.split('.a:',1)
            owner='dependency-program-data';source=archive.split('/')[-1]+'.a:'+member
        elif '@src@'in location:
            owner='project-compiled-data';source='src/'+location.rsplit('@src@',1)[1].replace('@','/')
        elif '@build@probe-source@'in location:
            owner='CC0-compiled-data';source='build/probe-source/'+location.rsplit('@build@probe-source@',1)[1].replace('@','/')
        else:continue
        objects.setdefault((fields[-1].split('.')[0],size),[]).append(dict(owner=owner,source=source))
        objects_exact.setdefault((fields[-1],size),[]).append(dict(owner=owner,source=source))
        objects_by_name.setdefault(fields[-1].split('.')[0],[]).append(dict(owner=owner,source=source))
    if work is None:raise ValueError('A private declaration-cache directory is required')
    work.mkdir(parents=True,exist_ok=True)
    source_index=SourceIndex(root,work)
    outputs={}
    sections={}
    for section in elf.sections:
        if not(section.flags&2) or section.kind==8 or not section.size:
            continue
        overlay=re.fullmatch(r'\.zone_(R[01345678])',section.name)
        file='cd/ZT'+overlay[1]+'.BIN' if overlay else 'cd/A.BIN'
        lma=elf.load_address(section)
        sections[section.index]=(section,file,lma)
    for file in sorted({file for _,file,_ in sections.values()}):
        members=[(section,lma)for section,name,lma in sections.values()if name==file]
        base=min(lma for _,lma in members)
        length=max(lma+s.size for s,lma in members)-base
        image=bytearray(length)
        # A gap between load sections is linker zero fill. Within a section,
        # attribution starts unknown until a symbol or code section owns it.
        mask=bytearray([1])*length
        for section,lma in members:
            offset=lma-base
            image[offset:offset+section.size]=elf.content(section)
            mask[offset:offset+section.size]=bytes(section.size)
        native=(root/file).read_bytes()
        if image!=native:raise ValueError('ELF reconstruction differs from '+file)
        outputs[file]=dict(bytes=length,sha256=hashlib.sha256(native).hexdigest(),base=base,
                           image=image,mask=mask,symbols=[],sections=[])
    for index,(section,file,lma) in sections.items():
        out=outputs[file];offset=lma-out['base']
        out['sections'].append(dict(name=section.name,offset=offset,bytes=section.size,executable=bool(section.flags&4)))
        # Executable sections contain functions, compiler pools and alignment.
        # Explicit generated data objects below take precedence over this class.
        if section.flags&4:
            out['mask'][offset:offset+section.size]=bytes([1])*section.size
    for symbol in elf.symbols:
        if not symbol['bytes'] or symbol['section']not in sections or symbol['type']not in (1,2):
            continue
        section,file,lma=sections[symbol['section']];out=outputs[file]
        offset=lma-out['base']+symbol['value']-section.address
        if not 0<=offset<=len(out['mask'])-symbol['bytes']:
            raise ValueError('Symbol outside linked file')
        origin=objects_exact.get((symbol['name'],symbol['bytes']),objects_exact.get((symbol['name'].split('.lto_priv.')[0],symbol['bytes']),
            objects.get((symbol['name'].split('.')[0],symbol['bytes']),[])))
        selected=evidence
        # LTO renumbers local static suffixes. An equal .45 in another input
        # object is not an identity proof for the linked .45.
        if origin and '.'not in symbol['name']:
            defining_units={o['source'].removesuffix('.o')+'.c'for o in origin if o['source'].startswith(('src/','build/'))}
            filtered={name:[e for e in evidence.get(name,[])if e.get('translation_unit')in defining_units]
                for name in source_names(symbol['name'])}
            if any(filtered.values()) or not defining_units:selected=filtered
        provenance=symbol_provenance(root,symbol,selected)
        if symbol['type']==2:
            provenance['evidence']=source_index.function(symbol['name'],objects_by_name.get(symbol['name'].split('.')[0],origin))
        if provenance['kind']=='unresolved':
            zero=not any(out['image'][offset:offset+symbol['bytes']])
            resolved=source_index.resolve(symbol,origin,zero)
            if resolved:
                if any(generated_evidence(e,root) for e in resolved):
                    provenance=dict(kind='derive',owner='generated-initializer',evidence=resolved)
                else:
                    owner='compiled-control-table' if symbol['name'].startswith('_CSWTCH.') else (
                        'linker-zero-fill' if zero else 'dependency-source-initializer' if all(e['source'].startswith(('.deps/','gcc/'))for e in resolved) else 'project-source-initializer')
                    provenance=dict(kind='derive'if owner in ('project-source-initializer','dependency-source-initializer')else'literal',owner=owner,evidence=resolved)
        row=dict(symbol=symbol['name'],offset=offset,bytes=symbol['bytes'],section=section.name,**provenance)
        out['symbols'].append(row)
        value={'unresolved':0,'literal':1,'derive':2}[row['kind']]
        # Named data wins over a function/pool span that aliases the same bytes.
        if symbol['type']==1:
            out['mask'][offset:offset+symbol['bytes']]=bytes([value])*symbol['bytes']
    # Linked binary assets have zero-sized STT_NOTYPE start labels. The range
    # length comes from the native converter output, not a guessed next symbol.
    assets={
        '_binary_assets_generated_sonic_bin_start':'assets/generated/sonic.bin',
        '_binary_assets_generated_hud_font_bin_start':'assets/generated/hud-font.bin',
        '_binary_assets_generated_hud_original_bin_start':'assets/generated/hud-original.bin',
        '_binary_assets_generated_title_card_art_bin_start':'assets/generated/title-card-art.bin',
        '_binary_build_sound_driver_driver_bin_start':'build/sound-driver/driver.bin',
    }
    for symbol in elf.symbols:
        if symbol['name']not in assets or symbol['section']not in sections:
            continue
        source=assets[symbol['name']];section,file,lma=sections[symbol['section']];out=outputs[file]
        offset=lma-out['base']+symbol['value']-section.address;data=(root/source).read_bytes()
        if out['image'][offset:offset+len(data)]!=data:raise ValueError('Linked asset range differs')
        firmware=source.startswith('build/sound-driver/')
        kind='literal'if firmware else'derive'
        out['mask'][offset:offset+len(data)]=bytes([1 if firmware else 2])*len(data)
        out['symbols'].append(dict(symbol=symbol['name'],offset=offset,bytes=len(data),section=section.name,
            kind=kind,owner='PoneSound-MIT-program'if firmware else'linked-asset-blob',
            evidence=[dict(source='tools/ponesound/driver.c',line=1,artifact=source,
                source_sha256=hashlib.sha256((root/'tools/ponesound/driver.c').read_bytes()).hexdigest())] if firmware else
                [dict(source=source,sha256=hashlib.sha256(data).hexdigest())]))
    # A data relocation to a function/section is program linkage, not retail
    # payload. Never let relocation evidence overwrite a generated initializer.
    for reloc in elf.sections:
        if reloc.kind!=4 or reloc.info not in sections:
            continue
        target,file,lma=sections[reloc.info];out=outputs[file]
        for at in range(reloc.offset,reloc.offset+reloc.size,reloc.entry_size):
            address,info,addend=struct.unpack_from(elf.endian+'IIi',elf.data,at)
            symbol=elf.symbols[info>>8]
            if symbol['section']not in sections:continue
            if info&255!=1:continue # R_SH_DIR32
            offset=lma-out['base']+address-target.address
            if 0<=offset<=len(out['mask'])-4 and not any(v==2 for v in out['mask'][offset:offset+4]):
                out['mask'][offset:offset+4]=bytes([1])*4
    # GCC merges anonymous strings across translation units. Attribute each
    # actual string to its .i line marker before admitting it as program text.
    # Generated strings are handled by table recipes and never by this rule.
    for unit in sorted((root/'build/saturn').glob('*.i')):
        source=None;line_number=0;unit_hash=hashlib.sha256(unit.read_bytes()).hexdigest()
        for line in unit.open(errors='replace'):
            marker=re.match(r'#\s+(\d+)\s+"([^"]+)"',line)
            if marker:
                source=public_source_path(marker[2],root);line_number=int(marker[1])-1;continue
            line_number+=1
            if not source or generated_input(source,root):continue
            if not source.startswith(('src/','build/probe-source/','.toolchain/')):continue
            groups=list(re.finditer(r'"(?:\\.|[^"\\])*"(?:\s*"(?:\\.|[^"\\])*")*',line))
            groups+=list(re.finditer(r'"(?:\\.|[^"\\])*"',line))
            for match in groups:
                try:data=b''.join(c_string(token)for token in re.findall(r'"(?:\\.|[^"\\])*"',match[0]))+b'\0'
                except (ValueError,SyntaxError,UnicodeEncodeError):continue
                if len(data)<2:continue
                for out in outputs.values():
                    at=out['image'].find(data)
                    while at>=0:
                        if 0 in out['mask'][at:at+len(data)] and 2 not in out['mask'][at:at+len(data)]:
                            out['mask'][at:at+len(data)]=bytes([1])*len(data)
                            out['symbols'].append(dict(symbol='<anonymous-string>',offset=at,bytes=len(data),
                                section='.rodata',kind='literal',owner='source-string',evidence=[dict(source=source,
                                line=line_number,translation_unit_sha256=unit_hash,
                                string_sha256=hashlib.sha256(data).hexdigest())]))
                        at=out['image'].find(data,at+1)
    # The accepted link map attributes unnamed compiler control tables to
    # input objects. Only bare .rodata contributions qualify here; named data
    # and merged string sections still need their own initializer evidence.
    link_map=root/'build/unknown-program.map'
    if link_map.is_file():
        text=link_map.read_text();map_hash=hashlib.sha256(text.encode()).hexdigest()
        for match in re.finditer(r'^ \.rodata\s+0x([0-9a-f]+)\s+0x([0-9a-f]+)\s+(\S+)',text,re.M):
            address,size=int(match[1],16),int(match[2],16);object_path=match[3]
            if not ('ltrans'in object_path or '@src@'in object_path or '@build@probe-source@'in object_path):continue
            for out in outputs.values():
                start=address-out['base'];end=start+size
                if not 0<=start<end<=len(out['mask']):continue
                # Generated named objects have already set DERIVE and cannot
                # be overwritten by the compiler-table classification.
                for at in range(start,end):
                    if out['mask'][at]==0:out['mask'][at]=1
                origins=[]
                if '@src@'in object_path:
                    source='src/'+object_path.split('@src@')[-1].removesuffix('.o')+'.c'
                    if source in source_index.files:origins=[source_index.row(source,1)]
                for reloc in elf.sections:
                    if reloc.kind!=4:continue
                    code=elf.sections[reloc.info]
                    if not code.flags&4:continue
                    for pos in range(reloc.offset,reloc.offset+reloc.size,reloc.entry_size):
                        location,info,_=struct.unpack_from(elf.endian+'IIi',elf.data,pos)
                        if info&255!=1:continue
                        pointer=int.from_bytes(elf.data[code.offset+location-code.address:code.offset+location-code.address+4],'big')
                        if not address<=pointer<address+size:continue
                        for fun in elf.symbols:
                            if fun['type']==2 and fun['section']==code.index and fun['value']<=location<fun['value']+fun['bytes']:
                                origins.extend(source_index.function(fun['name']))
                if not origins:
                    # LTO may remove the referencing function's standalone name.
                    # Retain the source-defined link placement and all source
                    # units, rather than claiming that the temporary object is
                    # an ownership proof.
                    origins=[source_index.row('src/saturn.x',1,attribution='LTO control table link placement')]
                out['symbols'].append(dict(symbol='<compiler-anonymous-rodata>',offset=start,bytes=size,
                    section='.rodata',kind='literal',owner='compiled-control-table',evidence=[dict(
                        **e,link_map_sha256=map_hash)for e in origins]))
    # Library assertion text is compiled program data. Compare each complete
    # string with its original object, not merely printable bytes in A.BIN.
    library=root/'.toolchain/sh-elf/lib/libyaul.a'
    library_hash=hashlib.sha256(library.read_bytes()).hexdigest()
    for member,body in archive_members(library):
        if not body.startswith(b'\x7fELF'):continue
        obj=Elf(member,body)
        for section in obj.sections:
            if '.str'not in section.name or not section.flags&2:continue
            for text in obj.content(section).split(b'\0'):
                if len(text)<2:continue
                data=text+b'\0'
                for out in outputs.values():
                    at=out['image'].find(data)
                    while at>=0:
                        if 0 in out['mask'][at:at+len(data)] and 2 not in out['mask'][at:at+len(data)]:
                            out['mask'][at:at+len(data)]=bytes([1])*len(data)
                            out['symbols'].append(dict(symbol='<library-string>',offset=at,bytes=len(data),
                                section='.rodata',kind='literal',owner='dependency-program-string',evidence=[dict(
                                source=source_index.by_stem[Path(member).stem][0],line=1,
                                archive='libyaul.a',archive_sha256=library_hash,object=member,
                                object_sha256=hashlib.sha256(body).hexdigest(),input_section=section.name,
                                string_sha256=hashlib.sha256(data).hexdigest())]))
                        at=out['image'].find(data,at+1)
    for out in outputs.values():
        # Only zero padding between attributed neighbors can inherit a class.
        mask,image=out['mask'],out['image']
        for row in intervals(mask):
            if row['kind']!='unresolved':continue
            start,end=row['offset'],row['offset']+row['bytes']
            if any(image[start:end]):continue
            neighbors={v for v in [mask[start-1]if start else 0,mask[end]if end<len(mask)else 0]if v}
            if neighbors:
                inherited=2 if 2 in neighbors else 1
                mask[start:end]=bytes([inherited])*(end-start)
        # STT_FUNC may end before its compiler pool/alignment. Named data
        # already owns its bytes and always overrides this executable context.
        for section in out['sections']:
            if not section['executable']:continue
            start,end=section['offset'],section['offset']+section['bytes']
            functions=[s for s in out['symbols'] if s['owner']=='compiled-function-and-pools' and start<=s['offset']<end]
            occupied=bytearray(end-start)
            for s in out['symbols']:
                a,b=max(start,s['offset']),min(end,s['offset']+s['bytes'])
                if a<b:occupied[a-start:b-start]=bytes([1])*(b-a)
            for gap in intervals(occupied):
                if gap['kind']!='unresolved':continue
                a,b=start+gap['offset'],start+gap['offset']+gap['bytes']
                if not any(image[a:b]) or not all(mask[a:b]):continue
                previous=[f for f in functions if f['offset']<=a]
                adjacent=max(previous,key=lambda f:f['offset']) if previous else min(functions,key=lambda f:f['offset']) if functions else None
                if adjacent:
                    out['symbols'].append(dict(symbol='<function-pool-or-alignment>',offset=a,bytes=b-a,
                        section=section['name'],kind='literal',owner='compiled-function-and-pools',evidence=adjacent['evidence']))
        out['ranges']=intervals(mask)
        out['unresolved_bytes']=sum(r['bytes']for r in out['ranges']if r['kind']=='unresolved')
        del out['mask'];del out['image']
    return dict(schema=1,policy='source-data-provenance-v2',elf_sha256=elf.sha256,programs=outputs)
