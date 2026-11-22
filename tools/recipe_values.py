"""Deterministic C-initializer reader and big-endian data serializer.

The browser reads converter output text. Schemas contain C ABI layout only;
pointer bindings contain approved linked addresses, never art/table values.
"""
import ast
from dataclasses import dataclass
import hashlib
import re
import struct


def c_string(token):
    """C byte-string escapes, without Python's Unicode re-encoding."""
    result=bytearray();body=token[1:-1];at=0
    escapes={'a':7,'b':8,'t':9,'n':10,'v':11,'f':12,'r':13,'e':27,'\\':92,'"':34,"'":39,'?':63}
    while at<len(body):
        char=body[at];at+=1
        if char!='\\':result.extend(char.encode());continue
        if at==len(body):raise ValueError('Truncated C escape')
        char=body[at];at+=1
        if char in escapes:result.append(escapes[char])
        elif char in '01234567':
            m=re.match(r'[0-7]{0,2}',body[at:]);digits=char+m[0];at+=len(m[0]);result.append(int(digits,8)%256)
        elif char=='x':
            m=re.match(r'[0-9a-fA-F]+',body[at:])
            if not m:raise ValueError('Invalid hexadecimal C escape')
            at+=len(m[0]);result.append(int(m[0],16)%256)
        elif char=='\n':pass
        else:raise ValueError('Unsupported C escape')
    return bytes(result)


@dataclass
class Leaf:
    text: str
    index: int
    designator: str = ''


@dataclass
class Group:
    items: list
    designator: str = ''


def uncomment(text):
    tokens=re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|/\*.*?\*/|//[^\n]*',re.S)
    return tokens.sub(lambda m:''.join('\n'if c=='\n'else' 'for c in m[0])if m[0].startswith(('/',))else m[0],text)


class Reader:
    def __init__(self,text,start):
        self.text=text;self.at=start;self.index=0

    def whitespace(self):
        while self.at<len(self.text)and self.text[self.at].isspace():self.at+=1

    def item(self):
        self.whitespace();designator=''
        match=re.match(r'((?:\.\w+|\[[^\]]+\])+)\s*=\s*',self.text[self.at:])
        if match:designator=match[1];self.at+=match.end();self.whitespace()
        if self.at>=len(self.text):raise ValueError('Truncated initializer')
        if self.text[self.at]=='{':
            self.at+=1;items=[]
            while True:
                self.whitespace()
                if self.at>=len(self.text):raise ValueError('Unclosed initializer')
                if self.text[self.at]=='}':self.at+=1;break
                items.append(self.item());self.whitespace()
                if self.text[self.at]==',':self.at+=1
                elif self.text[self.at]!='}':raise ValueError('Expected initializer separator')
            return self.designated(Group(items,designator))
        start=self.at;quote=None;escape=False;paren=bracket=0
        while self.at<len(self.text):
            c=self.text[self.at]
            if escape:escape=False
            elif quote:
                if c=='\\':escape=True
                elif c==quote:quote=None
            elif c in "'\"":quote=c
            elif c=='(':paren+=1
            elif c==')':paren-=1
            elif c=='[':bracket+=1
            elif c==']':bracket-=1
            elif c in ',};'and not(paren or bracket):break
            self.at+=1
        value=self.text[start:self.at].strip()
        if not value:raise ValueError('Empty initializer expression')
        leaf=Leaf(value,self.index,designator);self.index+=1;return self.designated(leaf)

    @staticmethod
    def designated(node):
        parts=re.findall(r'\.\w+|\[[^\]]+\]',node.designator)
        if len(parts)<2:return node
        node.designator=parts[-1]
        for part in reversed(parts[:-1]):node=Group([node],part)
        return node


def initializer(text,name,occurrence=0):
    text=uncomment(text)
    matches=list(re.finditer(r'\b'+re.escape(name)+r'\s*(?:\[[^\]]*\]\s*)*(?:\)\s*\([^;={}]*\))?\s*=\s*',text))
    if occurrence>=len(matches):raise ValueError('Initializer declaration is missing')
    reader=Reader(text,matches[occurrence].end())
    return reader.item()


def number(expression,defines=None):
    defines=defines or {}
    expression=expression.strip()
    expression=re.sub(r'\(\s*void\s*\(\s*\*\s*\)\s*\([^)]*\)\s*\)','',expression)
    if expression.strip() in defines:return defines[expression.strip()]
    expression=re.sub(r'\(\s*(?:const\s+)?[A-Za-z_]\w*_t\s*\*?\s*\)','',expression)
    expression=re.sub(r'\(\s*(?:const\s+)?void\s*\*\s*\)','',expression)
    expression=re.sub(r'\((?:const\s+)?(?:unsigned\s+|signed\s+)?(?:char|short|int|long|u?int\d+_t)\s*\)', '',expression)
    expression=re.sub(r'(?<=[0-9a-fA-F])[uUlL]+\b','',expression)
    if re.fullmatch(r'[-+]?(?:\d+\.\d*|\.\d+)(?:[eE][+-]?\d+)?[fF]?',expression.strip()):
        return float(expression.rstrip('fF'))
    expression=expression.strip()
    while expression.startswith('(')and expression.endswith(')'):
        depth=0;complete=True
        for i,c in enumerate(expression):
            depth+=(c=='(')-(c==')')
            if depth==0 and i<len(expression)-1:complete=False;break
        if not complete:break
        expression=expression[1:-1].strip()
    if '?'in expression:
        depth=0;question=None;nest=0
        for i,c in enumerate(expression):
            depth+=(c=='(')-(c==')')
            if c=='?'and depth==0:
                if question is None:question=i
                else:nest+=1
            elif c==':'and depth==0 and question is not None:
                if nest:nest-=1
                else:return number(expression[question+1:i]if number(expression[:question],defines)else expression[i+1:],defines)
    tree=ast.parse(expression,mode='eval')
    def value(n):
        if isinstance(n,ast.Constant)and isinstance(n.value,(int,float)):return n.value
        if isinstance(n,ast.Constant)and isinstance(n.value,str)and len(n.value)==1:return ord(n.value)
        if isinstance(n,ast.Name):
            if n.id=='NULL':return 0
            if n.id in defines:return defines[n.id]
        if isinstance(n,ast.Compare):
            left=value(n.left)
            for op,right_node in zip(n.ops,n.comparators):
                right=value(right_node)
                operations={ast.Eq:lambda:left==right,ast.NotEq:lambda:left!=right,ast.Lt:lambda:left<right,ast.LtE:lambda:left<=right,ast.Gt:lambda:left>right,ast.GtE:lambda:left>=right}
                if type(op)not in operations or not operations[type(op)]():return 0
                left=right
            return 1
        if isinstance(n,ast.UnaryOp):
            v=value(n.operand)
            if isinstance(n.op,ast.USub):return -v
            if isinstance(n.op,ast.UAdd):return v
            if isinstance(n.op,ast.Invert):return ~v
        if isinstance(n,ast.BinOp):
            a,b=value(n.left),value(n.right)
            def divide():return (abs(a)//abs(b))*(-1 if(a<0)!=(b<0)else 1)
            ops={ast.Add:lambda:a+b,ast.Sub:lambda:a-b,ast.Mult:lambda:a*b,ast.Div:divide,
                 ast.FloorDiv:divide,ast.Mod:lambda:a-divide()*b,ast.LShift:lambda:a<<b,
                 ast.RShift:lambda:a>>b,ast.BitOr:lambda:a|b,ast.BitAnd:lambda:a&b,ast.BitXor:lambda:a^b}
            if type(n.op)in ops:return ops[type(n.op)]()
        raise ValueError('Unsupported numeric initializer expression: '+ast.unparse(n)[:160])
    return value(tree.body)


def defines(text):
    result={}
    for key,body in re.findall(r'^\s*#define\s+(\w+)\s+([^\n]+)',uncomment(text),re.M):
        try:result[key]=number(body,result)
        except (ValueError,SyntaxError,ZeroDivisionError):pass
    return result


def expression_hash(text):
    return hashlib.sha256(' '.join(text.split()).encode()).hexdigest()


def serialize(schema,node,constants=None,pointer=None):
    output=bytearray(schema['size']);constants=constants or {}
    class Cursor:
        def __init__(self,items):self.items=items;self.at=0
        def next(self):
            if self.at>=len(self.items):return None
            item=self.items[self.at];self.at+=1;return item

    def write(kind,item,offset):
        if item is None:return
        category=kind['kind']
        if category=='bits':
            item=item.items[0]if isinstance(item,Group)else item
            value=int(number(item.text,constants))
            for j in range(kind['width']):
                bit=(offset*8)+kind['bit']+j;mask=1<<(7-bit%8)
                if value&(1<<(kind['width']-1-j)):output[bit//8]|=mask
                else:output[bit//8]&=255-mask
            return
        if category in ('integer','float','pointer'):
            while isinstance(item,Group):
                if len(item.items)>1:raise ValueError('Multiple values for scalar initializer')
                item=item.items[0]if item.items else None
            if item is None:return
            if category=='pointer':
                try:value=number(item.text,constants)
                except (ValueError,SyntaxError):
                    if pointer is None:raise ValueError('Pointer binding is missing')
                    value=pointer(item,offset,kind)
                if not isinstance(value,int):raise ValueError('Non-integer pointer value')
                output[offset:offset+4]=(value%2**32).to_bytes(4,'big')
            elif category=='float':
                output[offset:offset+kind['size']]=struct.pack('>f'if kind['size']==4 else'>d',number(item.text,constants))
            else:
                value=number(item.text,constants)
                if not isinstance(value,int):raise ValueError('Float in integer initializer')
                width=kind['size'];output[offset:offset+width]=(value%(1<<(width*8))).to_bytes(width,'big')
            return
        if category=='array'and isinstance(item,Leaf)and item.text.startswith('"')and kind['element']['size']==1:
            parts=re.findall(r'"(?:\\.|[^"\\])*"',item.text)
            raw=''.join(ast.literal_eval(p)for p in parts).encode()+b'\0'
            if len(raw)>kind['size']+1:raise ValueError('String exceeds character array')
            output[offset:offset+min(len(raw),kind['size'])]=raw[:kind['size']];return
        cursor=Cursor(item.items if isinstance(item,Group)else[item])
        aggregate(kind,cursor,offset)

    def aggregate(kind,cursor,offset):
        if kind['kind']=='array':
            index=0
            while cursor.at<len(cursor.items)and(index<kind['count']or cursor.items[cursor.at].designator):
                item=cursor.next()
                if item.designator:
                    if not item.designator.startswith('['):raise ValueError('Field designation in array')
                    index=number(item.designator[1:-1],constants)
                if not 0<=index<kind['count']:raise ValueError('Designated array index outside bounds')
                child=kind['element'];where=offset+index*child['size']
                if child['kind']in ('array','struct','union')and isinstance(item,Leaf)and not item.text.startswith('"'):
                    cursor.at-=1;aggregate(child,cursor,where)
                else:write(child,item,where)
                index+=1
        elif kind['kind']in ('struct','union'):
            fields=kind['fields'];index=0
            while cursor.at<len(cursor.items)and(index<len(fields)or cursor.items[cursor.at].designator):
                item=cursor.next()
                if item.designator:
                    names=[f['name']for f in fields]
                    if not item.designator.startswith('.'):raise ValueError('Unknown designated field')
                    if item.designator[1:]not in names:
                        anonymous=next((f for f in fields if not f['name'] and any(g['name']==item.designator[1:]for g in f['type'].get('fields',[]))),None)
                        if anonymous is None:raise ValueError('Unknown designated field')
                        write(anonymous['type'],Group([item]),offset+anonymous['offset']);continue
                    index=names.index(item.designator[1:])
                if index>=len(fields):raise ValueError('Excess struct initializer')
                field=fields[index];child=field['type'];where=offset+field['offset']
                if child['kind']in ('array','struct','union')and isinstance(item,Leaf)and not item.text.startswith('"'):
                    cursor.at-=1;aggregate(child,cursor,where)
                else:write(child,item,where)
                if kind['kind']=='union':break
                index+=1
        else:
            write(kind,cursor.next(),offset)
    write(schema,node,0)
    if len(output)!=schema['size']:raise ValueError('Initializer serializer changed its output bounds')
    return bytes(output)
