"""Re-read source macros and enums for source-derived object initializers.

Recipes contain source paths and hashes, never expanded table values. Expansion
is deterministic and fail-closed: every serialized object has an accepted hash.
"""
import functools
import ast
import re
from recipe_values import uncomment,number,initializer,Leaf,Group

TOKEN=re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|[A-Za-z_]\w*|\s+|.',re.S)


def definitions(text,initial=None):
    result={};live=dict(initial or {});stack=[];active=True
    text=uncomment(text).replace('\\\n','')
    def condition(body):
        body=re.sub(r'\bdefined\s*(?:\(\s*(\w+)\s*\)|(\w+))',lambda m:'1'if(m[1]or m[2])in live else'0',body)
        body=expand(body,live)
        body=re.sub(r'(?<=[0-9a-fA-F])[uUlL]+\b','',body)
        body=re.sub(r'\b[A-Za-z_]\w*\b','0',body)
        body=body.replace('&&',' and ').replace('||',' or ')
        body=re.sub(r'!(?!=)',' not ',body).strip()
        try:
            tree=ast.parse(body,mode='eval')
            allowed=(ast.Expression,ast.Constant,ast.UnaryOp,ast.BinOp,ast.BoolOp,ast.Compare,ast.operator,ast.unaryop,ast.boolop,ast.cmpop)
            if any(not isinstance(n,allowed)for n in ast.walk(tree)):return False
            return bool(eval(compile(tree,'source-conditional','eval'),{'__builtins__':{}},{}))
        except (ValueError,SyntaxError,TypeError,ZeroDivisionError):return False
    for line in text.splitlines():
        directive=re.match(r'\s*#\s*(\w+)\s*(.*)',line)
        if not directive:continue
        command,body=directive.groups()
        if command in ('if','ifdef','ifndef'):
            enabled=condition(body)if command=='if'else (body.strip()in live)==(command=='ifdef')
            stack.append((active,enabled));active=active and enabled;continue
        if command in ('elif','else'):
            parent,taken=stack[-1]
            enabled=not taken and (command=='else'or condition(body))
            stack[-1]=(parent,taken or enabled);active=parent and enabled;continue
        if command=='endif':active=stack.pop()[0];continue
        if not active:continue
        if command=='undef':live.pop(body.strip(),None);continue
        if command!='define':continue
        m=re.match(r'([A-Za-z_]\w*)(\([^)]*\))?(?:\s+(.*)|$)',body)
        if not m:continue
        args=None if m[2]is None else [v.strip()for v in m[2][1:-1].split(',')if v.strip()]
        result[m[1]]=(args,m[3]or'');live[m[1]]=result[m[1]]
    return result


def expand(text,macros,disabled=frozenset(),depth=0):
    if depth>64:raise ValueError('Source macro expansion exceeded 64 levels')
    tokens=TOKEN.findall(text);out=[];i=0
    while i<len(tokens):
        token=tokens[i];i+=1
        if token not in macros or token in disabled:out.append(token);continue
        parameters,body=macros[token]
        if parameters is not None:
            j=i
            while j<len(tokens)and tokens[j].isspace():j+=1
            if j==len(tokens)or tokens[j]!='(':out.append(token);continue
            level=1;args=[];part=[];j+=1
            while j<len(tokens)and level:
                t=tokens[j];j+=1
                if t=='(':level+=1
                elif t==')':level-=1
                if not level:break
                if t==','and level==1:args.append(''.join(part));part=[]
                else:part.append(t)
            if level:raise ValueError('Unclosed source macro invocation')
            if part or parameters:args.append(''.join(part))
            if len(args)!=len(parameters):raise ValueError('Source macro argument count differs: '+token)
            values=dict(zip(parameters,args));i=j
            body=''.join(values.get(t,t)for t in TOKEN.findall(body))
            body=re.sub(r'\s*##\s*','',body)
        out.append(expand(body,macros,disabled|{token},depth+1))
    return ''.join(out)


@functools.lru_cache(maxsize=128)
def context(root,paths):
    from pathlib import Path
    texts=[(Path(root)/p).read_text()for p in paths]
    macros={name:(None,'1')for name in ('__sh__','__SH__','__GNUC__','__STDC__','__LIBYAUL__','R1','R11A','SCD_ZONE_R5','SCD_REQUIRE_ZONE_TERRAIN','SCD_ZONE_OVERLAY')}
    for text in texts:macros.update(definitions(text,macros))
    macros['NULL']=(None,'0')
    constants={'NULL':0,'true':1,'false':0}
    for bits in (8,16,32,64):
        constants[f'UINT{bits}_MAX']=(1<<bits)-1
        constants[f'INT{bits}_MAX']=(1<<(bits-1))-1;constants[f'INT{bits}_MIN']=-(1<<(bits-1))
    for name,(args,body)in macros.items():
        if args is not None:continue
        try:constants[name]=number(expand(body,macros,{name}),constants)
        except (ValueError,SyntaxError,TypeError,KeyError,ZeroDivisionError):pass
    for text in texts:
        for body in re.findall(r'\benum\s*(?:\w+\s*)?\{([^{}]*)\}',uncomment(text),re.S):
            current=-1
            for item in body.split(','):
                pair=item.strip().split('=',1);name=pair[0].strip()
                if not re.fullmatch(r'\w+',name):continue
                try:current=number(expand(pair[1],macros),constants)if len(pair)==2 else current+1
                except (ValueError,SyntaxError,TypeError,KeyError):continue
                constants[name]=current
    return macros,constants


def source_initializer(text,name,occurrence,macros):
    # Preprocessor directives can appear inside an initializer. Read their
    # definitions above but remove directive lines before token expansion.
    clean=re.sub(r'(?m)^\s*#.*$','',uncomment(text).replace('\\\n',''))
    clean=re.sub(r'__attribute__\s*\(\((?:[^()]|\([^()]*\))*\)\)','',clean)
    clean=re.sub(r'\b__(?:aligned|used|unused|uncached|section)\b(?:\([^)]*\))?','',clean)
    try:node=initializer(clean,name,occurrence)
    except ValueError:
        lines=[line for line in clean.splitlines()if re.search(r'\b[A-Z][A-Z0-9_]*\s*\([^;]*\b'+re.escape(name)+r'\b',line)]
        if len(lines)!=1:raise
        node=initializer(expand(lines[0],macros),name,occurrence)
    def render(n):
        prefix=(n.designator+'=')if n.designator else''
        return prefix+('{'+','.join(render(v)for v in n.items)+'}'if isinstance(n,Group)else expand(n.text,macros))
    return initializer('_recipe_value='+render(node)+';','_recipe_value')


def dependency_unit(root,source,work):
    """Host-only SDK type query; no compiled bytes are emitted or distributed."""
    from pathlib import Path
    import hashlib,subprocess
    root=Path(root);work=Path(work)
    key=hashlib.sha256(source.encode()+(root/source).read_bytes()).hexdigest()
    unit=work/(key+'.sdk.i')
    if unit.exists():return unit
    parent=source
    if source.endswith('.inc'):
        candidates=[p for p in (root/source).parent.glob('*.c')if Path(source).name in p.read_text()]
        if len(candidates)!=1:
            candidates=[p for p in (root/'.deps/libyaul/libyaul').rglob('*.c')if Path(source).name in p.read_text()]
        if len(candidates)!=1:
            # Includes may include other .inc files (the console parser).
            includes=[p for p in (root/source).parent.glob('*.inc')if Path(source).name in p.read_text()]
            candidates=[p for p in (root/source).parent.glob('*.c')if any(q.name in p.read_text()for q in includes)]
        if len(candidates)!=1:raise ValueError('SDK include has no unique translation unit: '+source)
        parent=candidates[0].relative_to(root).as_posix()
    if source.startswith('.deps/gcc-'):
        # GCC's QI mode is one byte. This query introduces no values; the
        # initializer is always read from the pinned original C source.
        unit.write_text('typedef unsigned char UQItype;\n# 1 "'+source+'"\n'+(root/source).read_text().split('#ifdef L_clz\n',1)[1].split('#endif',1)[0])
        return unit
    sdk='.deps/libyaul/libyaul'
    include=['','bup','ip','libc/libc','kernel','kernel/dbgio','gamemath','scu',
        'scu/bus/a/cs0/arp','scu/bus/a/cs0/dram-cart','scu/bus/a/cs0/flash','scu/bus/a/cs0/usb-cart',
        'scu/bus/a/cs2/cd-block','scu/bus/b/scsp','scu/bus/b/vdp','scu/bus/cpu','scu/bus/cpu/smpc']
    command=[str(root/'.toolchain/bin/sh-elf-gcc'),'-E','-ffreestanding','-std=gnu11',
        *[arg for name in include for arg in('-I',str(Path(sdk)/name))],parent]
    result=subprocess.run(command,cwd=root,capture_output=True,text=True)
    if result.returncode:
        unit.with_suffix('.errors').write_text(result.stderr)
        raise ValueError('SDK metadata preprocessing failed: '+source)
    def marker(m):
        path=Path(m[2])
        if path.is_absolute()or '..'in path.parts:
            try:path=(root/path).resolve().relative_to(root)
            except ValueError:return m[0]
        return '# '+m[1]+' "'+path.as_posix()+'"'+m[3]
    unit.write_text(re.sub(r'(?m)^#\s+(\d+)\s+"([^"]+)"([^\n]*)',marker,result.stdout))
    return unit


def context_paths(root,unit,source):
    paths=[]
    for name in re.findall(r'(?m)^#\s+\d+\s+"([^"]+)"',unit.read_text()):
        if name.startswith(('src/','assets/generated/','build/probe-source/','.deps/libyaul/','.deps/gcc-')) and (root/name).is_file() and name not in paths:paths.append(name)
    if source not in paths:paths.append(source)
    # Initializer-local macros must take precedence over including source units.
    paths.remove(source);paths.append(source)
    return paths
