"""Value-free recipes for every generated program initializer, including overlays."""
import ast
import hashlib
import json
from pathlib import Path
import re
import struct
from recipe_elf import Elf, source_names, source_aliases, generated_input, generated_evidence
from recipe_types import Types
from recipe_dwarf import DwarfTypes
from recipe_source import dependency_unit,context_paths,context,source_initializer
from recipe_values import Leaf, Group, initializer, serialize, defines, number, expression_hash, uncomment, c_string

_slice_inputs={}


def slice_source(row,root):
    if row['codec']=='input-slice':
        role,name=row['role'],row['source_name']
        if '/'in name or '\\'in name or name in ('.','..'):raise ValueError('Unsafe input-slice name')
        if role=='jp':path=(root/'assets/private/sonic-cd-japan.cue').resolve().parent/name
        elif role=='us':path=root/'build/retail'/name
        elif role=='bios':path=root/'assets/private'/name
        else:raise ValueError('Invalid input-slice role')
    elif row['codec']=='reference-slice':
        if not re.fullmatch(r'\.deps/libyaul/libyaul/ip/blobs/sys_(?:sec|are[jtue]|init)\.bin',row['source']):
            raise ValueError('Unapproved boot reference')
        path=root/row['source']
    elif row['codec']=='output-slice':
        source=Path(row['source'])
        if source.is_absolute()or '..'in source.parts or not row['source'].startswith(('assets/generated/','cd/')):
            raise ValueError('Unsafe converted-output slice')
        if re.fullmatch(r'cd/(?:A|ZTR[01345678])\.BIN',row['source']):raise ValueError('Circular program source')
        path=root/source
    else:raise ValueError('Unknown source-slice codec')
    return path


def enums(text):
    result={}
    for body in re.findall(r'\benum\s*(?:\w+\s*)?\{([^{}]*)\}',uncomment(text),re.S):
        current=-1
        for item in body.split(','):
            item=item.strip()
            if not item:continue
            pair=item.split('=',1);name=pair[0].strip()
            if not re.fullmatch(r'\w+',name):continue
            current=number(pair[1],result)if len(pair)==2 else current+1
            result[name]=current
    return result


def leaves(node):
    if isinstance(node,Leaf):yield node
    else:
        for item in node.items:yield from leaves(item)


def canonical(node):
    if isinstance(node,Leaf):return [node.designator,' '.join(node.text.split())]
    return [node.designator,[canonical(n)for n in node.items]]


def field_names(layout,node,aliases):
    """Undo macro renames of C designators, retaining compiler field offsets."""
    import copy
    layout=copy.deepcopy(layout);designators=set()
    def visit(n):
        designators.update(re.findall(r'\.(\w+)',n.designator))
        if isinstance(n,Group):
            for child in n.items:visit(child)
    visit(node)
    def fields(t):
        if 'element'in t:fields(t['element'])
        for field in t.get('fields',[]):
            alternatives=source_aliases(field['name'],aliases)&designators
            if field['name']not in designators and len(alternatives)==1:field['name']=alternatives.pop()
            fields(field['type'])
    fields(layout)
    return layout


def tree_hash(node):
    return hashlib.sha256(json.dumps(canonical(node),separators=(',',':')).encode()).hexdigest()


def build(root,work,provenance,input_root=None):
    input_root=input_root or root
    elf=Elf(root/'build/saturn/sonic-cd-saturn-prototype.elf')
    if elf.sha256!=provenance['elf_sha256']:raise ValueError('Provenance ELF differs')
    units={hashlib.sha256(p.read_bytes()).hexdigest():p for p in (root/'build/saturn').glob('*.i')}
    types={};sdk_types={};recipes=[];strings=[];copies=[];failures=[]
    aliases={}
    for alias_file in [*(root/'src').glob('*'),*(root/'build/probe-source').glob('*')]:
        if alias_file.suffix.lower() not in ('.c','.h','.inc'):continue
        for original,renamed in re.findall(r'^\s*#define\s+(\w+)\s+(\w+)\s*$',alias_file.read_text(),re.M):
            aliases.setdefault(renamed,[]).append(original)
    pointer_targets={}
    for symbol in elf.symbols:
        for name in source_names(symbol['name']):
            for alias in source_aliases(name,aliases):
                pointer_targets.setdefault((alias,symbol['section'],symbol['value']),[]).append(symbol)
    native={file:(root/file).read_bytes()for file in provenance['programs']}
    symbol_index={}
    for symbol in elf.symbols:
        if symbol['section']<len(elf.sections):
            section=elf.sections[symbol['section']]
            symbol_index.setdefault((symbol['name'],section.name,symbol['bytes']),[]).append(symbol)
    relocations={}
    for section in elf.sections:
        if section.kind!=4:continue
        for at in range(section.offset,section.offset+section.size,section.entry_size):
            offset,info,addend=struct.unpack_from(elf.endian+'IIi',elf.data,at)
            reference=elf.symbols[info>>8]
            relocations[(section.info,offset)]=dict(kind=info&255,symbol=reference['name'],
                symbol_value=reference['value'],addend=addend,reference_section=reference['section'])

    def pointer_binding(leaf,where,kind,symbol,expected,source,name,occurrence):
        value=int.from_bytes(expected[where:where+4],'big')
        relocation=relocations.get((symbol['section'],symbol['value']+where))
        if relocation is None or relocation['kind']!=1:
            raise ValueError('Generated pointer has no R_SH_DIR32 relocation: '+leaf.text[:160])
        reference=relocation['reference_section']
        if reference>=len(elf.sections)or not elf.sections[reference].flags&2:
            raise ValueError('Generated pointer is not program linkage')
        # SH --emit-relocs preserves a section relocation with the local
        # addend already in the linked word. Certify that word against the
        # initializer's named ELF target, rather than assuming RELA.addend
        # contains the entire section offset.
        if '"' not in leaf.text:
            text=re.sub(r'^\s*\([\w\s*]+\)\s*','',leaf.text)
            target=re.fullmatch(r'\s*&?\s*([A-Za-z_]\w*)\s*(?:\[\s*0\s*\]\s*)*',text)
            if target is None:
                raise ValueError('Unsupported symbolic pointer expression: '+leaf.text)
            candidates=pointer_targets.get((target[1],reference,value),[])
            if not candidates:
                raise ValueError('Generated pointer differs from its named ELF target')
            relocation=dict(relocation,target=target[1],target_value=value,
                            linked_section_offset=value-relocation['symbol_value'])
        row=dict(value=value,expression_sha256=expression_hash(leaf.text),relocation=relocation)
        # Anonymous strings from generated includes inherit DERIVE. They are
        # not automatically admitted by the rule for handwritten source text.
        if '"'in leaf.text:
            tokens=re.findall(r'"(?:\\.|[^"\\])*"',leaf.text)
            data=b''.join(c_string(t)for t in tokens)+b'\0'
            found=False
            for section in elf.sections:
                if section.kind==8 or not section.flags&2 or not section.address<=value<=section.address+section.size-len(data):continue
                if elf.content(section)[value-section.address:value-section.address+len(data)]!=data:continue
                overlay=re.fullmatch(r'\.zone_(R[01345678])',section.name)
                file='cd/ZT'+overlay[1]+'.BIN'if overlay else'cd/A.BIN'
                offset=elf.load_address(section)-provenance['programs'][file]['base']+value-section.address
                string=dict(file=file,offset=offset,bytes=len(data),codec='cstring',source=source,
                            variable=name,occurrence=occurrence,leaf=leaf.index,sha256=hashlib.sha256(data).hexdigest())
                if string not in strings:
                    if macro_paths:string['macro_sources']=macro_paths
                    strings.append(string)
                found=True;break
            if not found:raise ValueError('Generated string pointer does not match linked string storage')
        return row

    seen=set();literal_proofs=[]
    for file,program in provenance['programs'].items():
        for row in program['symbols']:
            verify_literal=False
            if row['kind']!='derive' and not verify_literal:continue
            key=(file,row['offset'],row['bytes'])
            if key in seen:continue
            expected=native[file][row['offset']:row['offset']+row['bytes']]
            if not any(expected):seen.add(key);continue
            if row['owner']=='linked-asset-blob':
                source=row['evidence'][0]['source'];data=(input_root/source).read_bytes()
                if data!=expected:raise ValueError('Linked asset input changed')
                copies.append(dict(file=file,offset=row['offset'],bytes=len(data),codec='copy',source=source,
                                   sha256=hashlib.sha256(data).hexdigest()))
                seen.add(key);continue
            name=row['symbol'][1:]if row['symbol'].startswith('_')else row['symbol']
            name=name.split('.')[0]
            errors=[];success=None
            symbols=symbol_index.get((row['symbol'],row['section'],row['bytes']),[])
            for evidence in row['evidence']:
                source=evidence.get('source');unit=units.get(evidence.get('translation_unit_sha256'))
                if not source:continue
                if unit is None and source.startswith('.deps/'):
                    try:unit=dependency_unit(root,source,work)
                    except ValueError as error:errors.append(str(error));continue
                if unit is None:continue
                name=evidence.get('variable',name)
                path=input_root/source
                if not path.is_file():errors.append('converter output missing');continue
                try:
                    if unit not in types:types[unit]=Types(unit,work,'m68k-unknown-none'if source.startswith('.deps/')else'wasm32-unknown-unknown')
                    declarations=[evidence] if evidence.get('compiler_declaration') else list(types[unit].declarations(name,source))
                    if not declarations:
                        from recipe_elf import compiler_declarations
                        declarations=compiler_declarations(unit,name,work)
                except ValueError as error:errors.append(str(error));continue
                text=path.read_text();constants=defines(text);constant_sources=[]
                macro_paths=[];macros=None
                if row['owner']in ('project-source-initializer','dependency-source-initializer'):
                    macro_paths=context_paths(root,unit,source)
                    macros,constants=context(str(input_root),tuple(macro_paths))
                    constants=dict(constants)
                # Enum values are project program constants, not converter
                # payload. Keep their source provenance and read them again
                # during browser serialization.
                if source=='src/background_r3_tables.inc':
                    enum_source='src/background_r3.c'
                    enum_text=(input_root/enum_source).read_text()
                    constants.update(enums(enum_text))
                    constant_sources.append(dict(source=enum_source,sha256=hashlib.sha256(enum_text.encode()).hexdigest()))
                raw_names=[name,*sorted(source_aliases(name,aliases)-{name})]
                raw_name=next((candidate for candidate in raw_names if re.search(r'\b'+re.escape(candidate)+r'\s*(?:\[[^\]]*\]\s*)*=\s*',text)),name)
                for declaration in declarations:
                    try:
                        if source.startswith('.deps/'):
                            if unit not in sdk_types:sdk_types[unit]=DwarfTypes(root,unit,work)
                            layout=sdk_types[unit].variable(name,row['bytes'])
                        else:layout=types[unit].schema(declaration['ctype'],row['bytes'])
                    except ValueError as error:errors.append(str(error));continue
                    if layout['size']!=row['bytes']:
                        errors.append(f'C type size differs from linked symbol: {declaration["ctype"]}: {layout["size"]} != {row["bytes"]}');continue
                    cleaned=uncomment(text)
                    matches=list(re.finditer(r'\b'+re.escape(raw_name)+r'\s*(?:\[[^\]]*\]\s*)*(?:\)\s*\([^;={}]*\))?\s*=',cleaned))
                    preferred=[i for i,m in enumerate(matches)if cleaned.count('\n',0,m.start())+1==evidence['line']]
                    for occurrence in preferred or range(max(1,len(matches))):
                        try:node=source_initializer(text,raw_name,occurrence,macros)if macros is not None else initializer(text,raw_name,occurrence)
                        except ValueError:break
                        actual_layout=field_names(layout,node,aliases)
                        sizes={}
                        for leaf in leaves(node):
                            for expr,star,var in re.findall(r'(sizeof\(\s*(\*?)\s*(\w+)\s*\))',leaf.text):
                                target=next((s for s in elf.symbols if s['name'].split('.')[0]=='_'+var),None)
                                target_decl=next(types[unit].declarations(var),None)
                                if target_decl is None:continue
                                try:target_layout=types[unit].schema(target_decl['ctype'],target['bytes']if target else None)
                                except ValueError:continue
                                sizes[expr]=target_layout['element']['size']if star else target_layout['size']
                            if unit in sdk_types:
                                for expr,typename in re.findall(r'(sizeof\(\s*([A-Za-z_]\w*)\s*\))',leaf.text):
                                    try:sizes[expr]=sdk_types[unit].sizeof(typename)
                                    except ValueError:pass
                            expanded=leaf.text
                            for expr,size in sizes.items():expanded=expanded.replace(expr,str(size))
                            if expanded!=leaf.text:
                                try:constants[leaf.text]=number(expanded,constants)
                                except (ValueError,SyntaxError):pass
                        for symbol in symbols:
                            if symbol['value']-elf.sections[symbol['section']].address+elf.load_address(elf.sections[symbol['section']])-program['base']!=row['offset']:continue
                            bindings={};before=len(strings)
                            def bind(leaf,where,kind):
                                record=pointer_binding(leaf,where,kind,symbol,expected,source,raw_name,occurrence)
                                bindings[str(leaf.index)]=record
                                return record['value']
                            try:
                                data=serialize(actual_layout,node,constants,bind)
                                if data!=expected:raise ValueError('Serialized bytes differ from accepted symbol; differing offsets '+str([i for i,(a,b)in enumerate(zip(data,expected))if a!=b]))
                            except (ValueError,SyntaxError,OverflowError,IndexError,KeyError)as error:
                                del strings[before:];errors.append(str(error));continue
                            success=dict(file=file,offset=row['offset'],bytes=row['bytes'],codec='initializer',
                                symbol=row['symbol'],source=source,variable=raw_name,occurrence=occurrence,
                                initializer_sha256=tree_hash(node),layout=actual_layout,pointers=bindings,
                                sizeof=sizes,constant_sources=constant_sources,macro_sources=macro_paths,
                                sha256=hashlib.sha256(data).hexdigest(),evidence=evidence)
                            break
                        if success:break
                    if success:break
                if success:break
            if success:
                if verify_literal:
                    row.update(kind='literal',owner='project-source-initializer',evidence=[success['evidence']])
                    literal_proofs.append(success)
                else:
                    # Ambiguous LTO locals remain DERIVE even if a handwritten
                    # equivalent is the successful producer. A byte match must
                    # not revive a generated-data literal permission.
                    row['evidence']=[success['evidence']]
                    recipes.append(success)
                seen.add(key)
            else:failures.append(dict(file=file,symbol=row['symbol'],offset=row['offset'],bytes=row['bytes'],
                                      reasons=sorted(set(errors))or['No matching compiler declaration']))
    # Anonymous strings can usually be re-read cheaply from original source.
    # Store only offsets/codecs; no string or initializer bytes enter metadata.
    for file,program in provenance['programs'].items():
        for symbol in program['symbols']:
            if symbol['kind']!='literal'or symbol['owner']not in ('source-string','dependency-program-string'):continue
            data=native[file][symbol['offset']:symbol['offset']+symbol['bytes']]
            if not data.endswith(b'\0'):continue
            for proof in symbol['evidence']:
                source=proof['source']
                if not source.startswith(('src/','.deps/libyaul/'))or not(input_root/source).is_file():continue
                raw=(input_root/source).read_bytes();start=raw.find(data[:-1]);mode='bytes'
                if start<0:
                    text=raw.decode()
                    for match in re.finditer(r'"(?:\\.|[^"\\])*"(?:\s*"(?:\\.|[^"\\])*")*',text):
                        try:decoded=b''.join(c_string(t)for t in re.findall(r'"(?:\\.|[^"\\])*"',match[0]))+b'\0'
                        except ValueError:continue
                        if decoded==data:
                            start=len(text[:match.start()].encode());count=len(match[0].encode());mode='c-string';break
                else:count=len(data)-1
                if start<0:continue
                recipe=dict(codec='source-text-string',file=file,offset=symbol['offset'],bytes=len(data),source=source,
                    source_offset=start,source_length=count,mode=mode,sha256=hashlib.sha256(data).hexdigest())
                if not any(t['file']==file and t['offset']==recipe['offset']and t['bytes']==recipe['bytes']for t in strings):strings.append(recipe)
                break
    covered={file:bytearray(program['bytes'])for file,program in provenance['programs'].items()}
    for row in [*recipes,*copies,*strings]:covered[row['file']][row['offset']:row['offset']+row['bytes']]=bytes([1])*row['bytes']
    remaining=[]
    for row in failures:
        if not all(covered[row['file']][row['offset']:row['offset']+row['bytes']]):remaining.append(row)
    if literal_proofs:
        from recipe_provenance import intervals
        for file,program in provenance['programs'].items():
            mask=bytearray(program['bytes'])
            for span in program['ranges']:mask[span['offset']:span['offset']+span['bytes']]=bytes([{'unresolved':0,'literal':1,'derive':2}[span['kind']]])*span['bytes']
            for proof in literal_proofs:
                if proof['file']==file:mask[proof['offset']:proof['offset']+proof['bytes']]=bytes([1])*proof['bytes']
            for symbol in program['symbols']:
                if symbol['kind']=='derive':mask[symbol['offset']:symbol['offset']+symbol['bytes']]=bytes([2])*symbol['bytes']
            program['ranges']=intervals(mask)
            program['unresolved_bytes']=sum(r['bytes']for r in program['ranges']if r['kind']=='unresolved')
    # Clang's diagnostic type spelling can contain absolute build paths.
    # Only its public source proof belongs in the recipe; ABI layouts above
    # already carry the complete value-free serialization schema.
    def public_proof(evidence):return {k:v for k,v in evidence.items()if k not in ('ctype','offset')}
    for program in provenance['programs'].values():
        for symbol in program['symbols']:symbol['evidence']=[public_proof(e)for e in symbol['evidence']]
    for row in [*recipes,*literal_proofs]:row['evidence']=public_proof(row['evidence'])
    return dict(schema=1,elf_sha256=elf.sha256,initializers=recipes,copies=copies,strings=strings,
                failures=remaining,literal_proofs=literal_proofs,coverage={file:sum(mask)for file,mask in covered.items()})


def materialize(row,root,tables=None):
    if row['codec']=='table-slice':
        index=row['source_table']
        if tables is None or type(index)is not int or not 0<=index<len(tables):raise ValueError('Missing source table')
        source=tables[index]
        if source['codec']not in ('initializer','copy','cstring','source-text-string'):raise ValueError('Circular table-slice source')
        if source['bytes']!=row['source_bytes']or source['sha256']!=row['source_sha256']:raise ValueError('Source table pin differs')
        offset,count=row['source_offset'],row['bytes']
        if type(offset)is not int or type(count)is not int or min(offset,count)<0 or offset+count>source['bytes']:raise ValueError('Table-slice exceeds source')
        data=materialize(source,root)[offset:offset+count]
        if hashlib.sha256(data).hexdigest()!=row['sha256']:raise ValueError('Table-slice checksum failed')
        return data
    if row['codec']in ('input-slice','output-slice','reference-slice'):
        path=slice_source(row,root);stat=path.stat()
        key=(str(path),stat.st_size,stat.st_mtime_ns,row['source_sha256'])
        if stat.st_size!=row['source_bytes']:raise ValueError('Source-slice input size differs')
        if key not in _slice_inputs:
            with path.open('rb')as stream:checksum=hashlib.file_digest(stream,'sha256').hexdigest()
            if checksum!=row['source_sha256']:raise ValueError('Source-slice input checksum failed')
            _slice_inputs[key]=True
        offset,count=row['source_offset'],row['bytes']
        if type(offset)is not int or type(count)is not int or min(offset,count)<0 or offset+count>stat.st_size:raise ValueError('Source-slice exceeds input')
        with path.open('rb')as stream:stream.seek(offset);data=stream.read(count)
        if len(data)!=count or hashlib.sha256(data).hexdigest()!=row['sha256']:raise ValueError('Source-slice checksum failed')
        return data
    source=(root/row['source']).read_bytes()
    if row['codec']=='source-text-string':
        fragment=source[row['source_offset']:row['source_offset']+row['source_length']]
        data=(fragment if row['mode']=='bytes'else b''.join(c_string(t)for t in re.findall(r'"(?:\\.|[^"\\])*"',fragment.decode())))+b'\0'
    elif row['codec']=='copy':data=source
    else:
        text=source.decode()
        if row.get('macro_sources'):
            macros,source_constants=context(str(root),tuple(row['macro_sources']))
            node=source_initializer(text,row['variable'],row['occurrence'],macros)
        else:node=initializer(text,row['variable'],row['occurrence'])
        if row['codec']=='cstring':
            leaf=next(l for l in leaves(node)if l.index==row['leaf'])
            data=b''.join(c_string(t)for t in re.findall(r'"(?:\\.|[^"\\])*"',leaf.text))+b'\0'
        else:
            if tree_hash(node)!=row['initializer_sha256']:raise ValueError('Converter initializer changed')
            def pointer(leaf,where,kind):
                binding=row['pointers'].get(str(leaf.index))
                if binding is None or binding['expression_sha256']!=expression_hash(leaf.text):raise ValueError('Pointer expression changed')
                return binding['value']
            constants=dict(source_constants)if row.get('macro_sources')else defines(text)
            for source in row.get('constant_sources',[]):
                enum_text=(root/source['source']).read_text()
                if hashlib.sha256(enum_text.encode()).hexdigest()!=source['sha256']:raise ValueError('Project constants changed')
                constants.update(enums(enum_text))
            for leaf in leaves(node):
                expanded=leaf.text
                for expr,size in row.get('sizeof',{}).items():expanded=expanded.replace(expr,str(size))
                if expanded!=leaf.text:constants[leaf.text]=number(expanded,constants)
            data=serialize(row['layout'],node,constants,pointer)
    if len(data)!=row['bytes']or hashlib.sha256(data).hexdigest()!=row['sha256']:
        raise ValueError('Derived symbol checksum failed')
    return data
