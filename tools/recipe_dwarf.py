"""Host-only SH GCC layout certificates. No object values enter recipes."""
import hashlib
import re
import subprocess


class DwarfTypes:
    def __init__(self,root,unit,work):
        key=hashlib.sha256(unit.read_bytes()).hexdigest();obj=work/(key+'.sh-layout.o');dump=work/(key+'.sh-layout.dwarf')
        if not dump.exists():
            command=[str(root/'.toolchain/bin/sh-elf-gcc'),'-m2','-mb','-O0','-ffreestanding','-g','-gdwarf-4',
                '-fno-eliminate-unused-debug-types','-c',str(unit),'-o',str(obj)]
            result=subprocess.run(command,cwd=root,capture_output=True,text=True)
            if result.returncode:
                obj.with_suffix('.errors').write_text(result.stderr);raise ValueError('SH SDK metadata compilation failed')
            result=subprocess.run([str(root/'.toolchain/bin/sh-elf-readelf'),'--debug-dump=info',str(obj)],capture_output=True,text=True,check=True)
            dump.write_text(result.stdout)
        self.nodes={};stack=[];current=None
        for line in dump.read_text().splitlines():
            m=re.match(r'\s*<(\d+)><([0-9a-f]+)>: Abbrev Number: \d+(?: \(DW_TAG_(\w+)\))?',line)
            if m:
                depth=int(m[1]);stack=stack[:depth]
                if not m[3]:current=None;continue
                current=dict(tag=m[3],children=[]);self.nodes[int(m[2],16)]=current
                if stack:stack[-1]['children'].append(current)
                stack.append(current);continue
            m=re.match(r'\s*<[0-9a-f]+>\s+DW_AT_(\w+)\s*:\s*(.*)',line)
            if m and current is not None:
                value=re.sub(r'^\(indirect[^)]*\):\s*','',m[2])
                current[m[1]]=value
        self.cache={}

    def referenced(self,node):
        value=node.get('type','');m=re.search(r'<0x([0-9a-f]+)>',value)
        if not m:raise ValueError('Missing DWARF type reference')
        return self.nodes[int(m[1],16)]

    @staticmethod
    def integer(value):return int(value.split()[0],0)

    def schema(self,node):
        key=id(node)
        if key in self.cache:return self.cache[key]
        tag=node['tag'];size=self.integer(node.get('byte_size','0'))
        if tag in ('typedef','const_type','volatile_type','restrict_type'):return self.schema(self.referenced(node))
        if tag in ('base_type','enumeration_type'):
            result=dict(kind='float'if 'float'in node.get('encoding','')else'integer',size=size)
        elif tag=='pointer_type':result=dict(kind='pointer',size=size or 4)
        elif tag=='array_type':
            result=self.schema(self.referenced(node))
            dimensions=[self.integer(n['count'])if 'count'in n else self.integer(n.get('upper_bound','-1'))+1 for n in node['children']if n['tag']=='subrange_type']
            for count in reversed(dimensions):result=dict(kind='array',size=count*result['size'],count=count,element=result)
        elif tag in ('structure_type','union_type'):
            fields=[]
            for field in node['children']:
                if field['tag']!='member':continue
                offset=self.integer(field.get('data_member_location','0'))
                if 'bit_size'in field:
                    bits=self.integer(field['bit_size']);bit=self.integer(field.get('bit_offset','0'))
                    if 'data_bit_offset'in field:
                        bit=self.integer(field['data_bit_offset']);offset=bit//8;bit%=8
                    child=dict(kind='bits',size=(bit+bits+7)//8,bit=bit,width=bits)
                else:child=self.schema(self.referenced(field))
                fields.append(dict(name=field.get('name',''),offset=offset,type=child))
            result=dict(kind='struct'if tag=='structure_type'else'union',size=size,fields=fields)
        else:raise ValueError('Unsupported SH metadata type: '+tag)
        self.cache[key]=result;return result

    def variable(self,name,expected):
        for node in self.nodes.values():
            if node['tag']=='variable'and node.get('name')==name and 'type'in node:
                schema=self.schema(self.referenced(node))
                if schema['size']==expected:return schema
        raise ValueError('No SH SDK variable layout of the accepted size: '+name)

    def sizeof(self,name):
        for node in self.nodes.values():
            if node.get('name')==name and node['tag']in ('typedef','structure_type','union_type','base_type'):
                return self.schema(node)['size']
        raise ValueError('No SH SDK sizeof type: '+name)
