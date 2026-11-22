"""Build value-free, 32-bit C layout schemas for converter initializers.

Clang is a maintainer-side metadata tool only. No compiler runs in the browser.
The emitted schema contains sizes/field offsets, not initializer values.
"""
import ast
import bisect
import hashlib
import re
import subprocess
from pathlib import Path


def integer(expression):
    expression=re.sub(r'(?<=[0-9a-fA-F])[uUlL]+\b','',expression.strip())
    tree=ast.parse(expression,mode='eval')
    def value(n):
        if isinstance(n,ast.Constant)and type(n.value)is int:return n.value
        if isinstance(n,ast.UnaryOp)and isinstance(n.op,ast.USub):return -value(n.operand)
        if isinstance(n,ast.BinOp):
            a,b=value(n.left),value(n.right)
            operations={ast.Add:lambda:a+b,ast.Sub:lambda:a-b,ast.Mult:lambda:a*b,
                        ast.FloorDiv:lambda:a//b,ast.Div:lambda:a//b,ast.LShift:lambda:a<<b,
                        ast.RShift:lambda:a>>b,ast.BitOr:lambda:a|b,ast.BitAnd:lambda:a&b}
            if type(n.op)in operations:return operations[type(n.op)]()
        raise ValueError('Nonconstant array dimension')
    return value(tree.body)


class Types:
    def __init__(self, unit, work, target='wasm32-unknown-unknown'):
        self.unit=Path(unit)
        self.work=work
        original=self.unit.read_text(errors='replace')
        packed_enums=set(re.findall(r'\btypedef\s+enum(?:\s+\w+)?\s*\{[^{}]*\}\s*__attribute__\s*\(\(\s*packed\s*\)\)\s*(\w+)\s*;',original,re.S))
        self.text=re.sub(r'__attribute__\s*\(\((?:[^()]|\([^()]*\))*\)\)',
                         lambda m:''.join('\n'if c=='\n'else' 'for c in m[0]),original)
        self.root=self.unit.resolve().parents[2]
        self.aliases={}
        self.records={}
        self.markers=[]
        offset=0;source=None;line_number=0
        for line in self.text.splitlines(keepends=True):
            m=re.match(r'#\s+(\d+)\s+"([^"]+)"',line)
            if m:source=m[2];line_number=int(m[1])-1
            else:line_number+=1
            self.markers.append((offset,source,line_number))
            offset+=len(line)
        self.offsets=[m[0]for m in self.markers]
        key=hashlib.sha256(original.encode()).hexdigest()
        layout=work/(key+'.metadata-v6-'+target+'.layouts')
        if not layout.exists():
            from recipe_elf import syntax_unit
            with layout.open('w')as out,(work/(key+'.errors')).open('w')as err:
                result=subprocess.run(['clang','-target',target,'-x','c','-fsyntax-only',
                    '-Wno-everything','-Xclang','-fdump-record-layouts-complete',str(syntax_unit(self.unit,work))],stdout=out,stderr=err)
            if result.returncode:raise ValueError('Clang layout extraction failed; inspect local error log')
        for block in layout.read_text().split('*** Dumping AST Record Layout')[1:]:
            lines=block.strip('\n').splitlines()
            header=re.match(r'\s*\d+\s*\| (\S.*)',lines[0])
            size=re.search(r'\[sizeof=(\d+), align=(\d+)',block)
            if not header or not size:continue
            fields=[]
            for line in lines[1:]:
                m=re.match(r'\s*(\d+)(?::(\d+)-(\d+))?\s*\| {3}(\S.*)',line)
                if not m:continue
                field=re.fullmatch(r'(.+?)\s+(\w+)',m[4])
                if field:
                    item=dict(name=field[2],offset=int(m[1]),ctype=field[1])
                    if m[2]is not None:item.update(bit=int(m[2]),width=int(m[3])-int(m[2])+1)
                    fields.append(item)
                elif m[4].startswith(('struct ','union ')):
                    fields.append(dict(name='',offset=int(m[1]),ctype=m[4]))
            self.records[self.key(header[1])]=dict(kind='union'if header[1].startswith('union ')else'struct',
                size=int(size[1]),fields=fields)
        # Primitive and named aliases, including pointer aliases.
        for match in re.finditer(r'\btypedef\s+([^;{}]+?)\s+(\w+)\s*;',self.text):
            body,name=match[1].strip(),match[2]
            if '('not in body:self.aliases[name]=body
        for m in re.finditer(r'\btypedef\s+[^;{}]*?\(\s*\*\s*(\w+)\s*\)\s*\([^;{}]*\)\s*;',self.text):self.aliases[m[1]]='void *'
        for m in re.finditer(r'\btypedef\s+enum(?:\s+\w+)?\s*\{[^{}]*\}\s*(\w+)\s*;',self.text,re.S):self.aliases[m[1]]='unsigned char'if m[1]in packed_enums else'unsigned int'
        # Anonymous records get their name only at the end of the typedef.
        for match in re.finditer(r'\btypedef\s+(struct|union)\s*(\w+)?\s*\{',self.text):
            depth=1;end=match.end()
            while depth and end<len(self.text):
                depth+=(self.text[end]=='{')-(self.text[end]=='}');end+=1
            alias=re.match(r'\s*(\w+)\s*;',self.text[end:])
            if not alias:continue
            if match[2]:target=match[1]+' '+match[2]
            else:
                at=self.text.index(match[1],match.start())
                source,line,col=self.location(at)
                target=f'{match[1]} (unnamed at {source}:{line}:{col})'
            self.aliases[alias[1]]=self.key(target)

    @staticmethod
    def key(value):
        value=re.sub(r'\b(?:const|volatile|restrict|__restrict|__restrict__)\b','',value)
        value=value.replace('(anonymous at','(unnamed at')
        value=value.replace('(unnamed struct at','(unnamed at').replace('(unnamed union at','(unnamed at')
        return ' '.join(value.split())

    def location(self,offset):
        start,source,line=self.markers[bisect.bisect_right(self.offsets,offset)-1]
        return source,line,offset-start+1

    def schema(self,ctype,expected_size=None,seen=()):
        ctype=self.key(ctype)
        dimensions=re.findall(r'\[([^\]]*)\]',ctype)
        if dimensions:
            base=re.sub(r'\[[^\]]*\]','',ctype).strip()
            child=self.schema(base,seen=seen)
            counts=[]
            for dim in dimensions:
                try:counts.append(integer(dim))
                except (ValueError,SyntaxError):counts.append(None)
            if None in counts:
                if counts.count(None)!=1 or expected_size is None:raise ValueError('Array bound unavailable')
                stride=child['size']
                for n in counts:
                    if n is not None:stride*=n
                if expected_size%stride:raise ValueError('Array size is not a multiple of its element')
                counts[counts.index(None)]=expected_size//stride
            for count in reversed(counts):
                child=dict(kind='array',count=count,size=count*child['size'],element=child)
            return child
        if '*'in ctype:return dict(kind='pointer',size=4)
        if ctype in seen:raise ValueError('Recursive non-pointer C type')
        if ctype in self.aliases:return self.schema(self.aliases[ctype],expected_size,(*seen,ctype))
        if ctype in self.records:
            record=self.records[ctype]
            return dict(kind=record['kind'],size=record['size'],fields=[dict(name=f['name'],offset=f['offset'],
                type=(dict(kind='bits',size=(f['bit']+f['width']+7)//8,bit=f['bit'],width=f['width'])if 'bit'in f else self.schema(f['ctype'],seen=(*seen,ctype))))for f in record['fields']])
        fixed=re.fullmatch(r'(?:u?int|__u?int)(8|16|32|64)_t',ctype)
        if fixed:return dict(kind='integer',size=int(fixed[1])//8)
        if ctype.startswith('enum '):return dict(kind='integer',size=4)
        words=' '.join(re.sub(r'\b(?:signed|unsigned)\b','',ctype).split()) or 'int'
        if words in ('char','_Bool'):size=1
        elif words in ('short','short int'):size=2
        elif words in ('int','long','long int','size_t','ptrdiff_t','intptr_t','uintptr_t'):size=4
        elif words in ('long long','long long int'):size=8
        elif words in ('float','double'):return dict(kind='float',size=4 if words=='float'else 8)
        else:raise ValueError('Unresolved C type: '+ctype)
        return dict(kind='integer',size=size)

    def declarations(self,name,source=None):
        found=False
        pattern=re.compile(r'\b'+re.escape(name)+r'\s*((?:\[[^\]\n]*\]\s*)*)(?P<function>\)\s*\([^;={}]*\))?\s*=')
        for match in pattern.finditer(self.text):
            file,line,col=self.location(match.start())
            public=file
            if file and Path(file).is_absolute():
                try:public=Path(file).relative_to(self.root).as_posix()
                except ValueError:continue
            if source is not None and public!=source:continue
            start=self.text.rfind('\n',0,match.start())+1
            prefix=self.text[start:match.start()]
            static=prefix.rfind('static ')
            if static>=0:prefix=prefix[static:]
            else:prefix=prefix[prefix.rfind(';')+1:]
            prefix=re.sub(r'\b(?:static|extern)\b','',prefix).strip()
            if match['function']:
                prefix=re.sub(r'\(\s*\*\s*(?:const\s*)?$', '*',prefix).strip()
            if re.search(r'\b(?:struct|union)\s*\{',prefix):
                record=re.search(r'\b(struct|union)\s*\{',prefix)
                # Match the actual declaration line, including its column.
                actual=self.text.rfind(record[1],start,match.start())
                file,ln,column=self.location(actual)
                prefix=f'{record[1]} (unnamed at {file}:{ln}:{column})'
            elif not re.fullmatch(r'[A-Za-z_][\w\s*]*',prefix):
                continue
            found=True
            yield dict(source=public,line=line,ctype=prefix+match[1],initializer_offset=match.end())
        if not found:
            from recipe_elf import compiler_declarations
            for row in compiler_declarations(self.unit,name,self.work):
                if row['initialized'] and (source is None or source==row['source']):yield row
