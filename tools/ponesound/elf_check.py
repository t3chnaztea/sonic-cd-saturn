"""Exact reviewed pure ELF checker; never executes target code."""
import hashlib,struct

def require(ok,why):
 if not ok:raise ValueError(why)

def sha(raw):return hashlib.sha256(raw).hexdigest()

def check_elf(raw,contract):
 require(type(raw)is bytes and 52<=len(raw)<=2*1024*1024,'ELF input bounds')
 require(raw[:7]==b'\x7fELF\x01\x02\x01','ELF class/endian/version')
 header=struct.unpack_from('>16sHHIIIIIHHHHHH',raw)
 _,typ,machine,version,entry,phoff,shoff,flags,ehsize,phsize,phnum,shsize,shnum,shstr=header
 require((typ,machine,version,entry,ehsize,shsize)==(2,4,1,contract['ELF']['expected_historical_e_entry'],52,40),'ELF header contract')
 require(0<shnum<=4096 and shstr<shnum and shoff>=52 and shoff+shnum*40<=len(raw),'Section table bounds')
 def area(off,size):
  require(0<=off<=len(raw)and 0<=size<=len(raw)-off,'ELF file range outside held input');return raw[off:off+size]
 def string(buf,off):
  require(0<=off<len(buf),'String offset outside table');end=buf.find(b'\0',off);require(end>=0,'Unterminated string');return buf[off:end].decode('ascii')
 sections=[]
 for i in range(shnum):
  x=struct.unpack_from('>10I',raw,shoff+i*40);sections.append(dict(index=i,name_offset=x[0],type=x[1],flags=x[2],address=x[3],offset=x[4],size=x[5],link=x[6],info=x[7],alignment=x[8],entry_size=x[9]))
 names=sections[shstr];require(names['type']==3,'Section name table type');namebytes=area(names['offset'],names['size'])
 for s in sections:
  s['name']=string(namebytes,s['name_offset']);require(s['type']!=6,'Dynamic section forbidden')
  require(not(s['type']in(4,9)and s['size']),'Unresolved relocation section forbidden')
  if s['type']!=8:area(s['offset'],s['size'])
  require(s['address']+s['size']<=0x100000000,'Section address overflow')
 alloc=sorted([s for s in sections if s['flags']&2 and s['size']],key=lambda s:s['address'])
 require(alloc and len({s['name']for s in alloc})==len(alloc),'Missing/duplicate allocated sections')
 allowed={'VECTORS':1,'.text':1,'.data':1,'.bss':8}
 require(all(s['name']in allowed and s['type']==allowed[s['name']]for s in alloc),'Unexpected allocated section/type')
 byname={s['name']:s for s in alloc};require(set(byname)==set(allowed),'Required allocated section missing')
 bound=contract['workspace']['communication_address'];prior=0
 for s in alloc:
  require(s['address']>=prior and s['address']+s['size']<=bound,'Allocated/BSS range overlaps or crosses communication')
  require(not s['alignment']or s['address']%s['alignment']==0,'Section address alignment');prior=s['address']+s['size']
 require(byname['.text']['address']==contract['workspace']['text_address'],'Text start changed')
 require(phnum>0 and phsize==32 and phoff+phnum*32<=len(raw),'Program table bounds')
 loads=[]
 for i in range(phnum):
  pt,off,va,pa,fs,ms,pflags,align=struct.unpack_from('>8I',raw,phoff+i*32)
  require(pt not in(2,3),'Dynamic/interpreter program segment forbidden')
  if pt==1:
   area(off,fs);require(fs<=ms and va==pa and va+ms<=bound,'Load segment bounds');loads.append((off,va,fs,ms))
 require(loads,'No static load segment')
 for s in alloc:
  require(any(va<=s['address']and s['address']+s['size']<=va+ms and(s['type']==8 or(s['offset']-off==s['address']-va and s['offset']+s['size']<=off+fs))for off,va,fs,ms in loads),'Allocated section not mapped by load segment')
 tables=[s for s in sections if s['type']==2];require(len(tables)==1,'Exactly one symbol table required');table=tables[0]
 require(table['entry_size']==16 and table['size']%16==0 and table['link']<shnum,'Symbol table shape');st=sections[table['link']];require(st['type']==3,'Symbol string table type');strings=area(st['offset'],st['size']);symbols={};undefined=[]
 for i in range(table['size']//16):
  no,value,size,info,other,index=struct.unpack_from('>IIIBBH',raw,table['offset']+i*16);name=string(strings,no)
  if not name:continue
  if index==0:undefined.append(name)
  require(index!=0xfff2,'Unallocated COMMON symbol '+name)
  symbols.setdefault(name,[]).append(dict(value=value,size=size,type=info&15,binding=info>>4,section=index))
 require(not undefined,'Undefined symbols: '+','.join(undefined))
 def symbol(name,kind=None):
  found=symbols.get(name,[]);require(len(found)==1,'Missing/ambiguous symbol '+name);s=found[0]
  require(s['section']!=0,'Undefined symbol '+name)
  if kind is not None:require(s['type']==kind,'Symbol type differs '+name)
  return s
 def content(name,size):
  sy=symbol(name,1);require(sy['size']==size and 0<sy['section']<shnum,'Symbol size/section '+name);sec=sections[sy['section']]
  require(sec['flags']&2 and sec['type']!=8 and sec['address']<=sy['value']and sy['value']+size<=sec['address']+sec['size'],'Symbol file mapping '+name)
  return area(sec['offset']+sy['value']-sec['address'],size)
 for name in contract['workspace']['required_symbols']:symbol(name)
 vector=byname['VECTORS'];require((vector['address'],vector['size'])==(0,1024),'Vector section shape')
 require(symbol('vecTable',1)['size']==1024 and symbol('vecTable')['value']==0 and symbol('__vectors')['value']==0,'Vector symbol ABI')
 words=struct.unpack('>256I',area(vector['offset'],vector['size']));require(words[:2]==(0x7fc00,0x408)and all(x==0x80000 for x in words[2:]),'Vector values changed')
 text=byname['.text'];code=area(text['offset'],text['size']);require(len(code)>=6 and symbol('lead_function',2)['value']==0x408,'Reset function location')
 opcode=struct.unpack_from('>H',code)[0]
 if opcode==0x4efa:target=0x40a+struct.unpack_from('>h',code,2)[0];jump='JMP pc-relative16'
 elif opcode==0x4ef9:target=struct.unpack_from('>I',code,2)[0];jump='JMP absolute32'
 else:raise ValueError('Unknown reset jump encoding; expected contract remains unchanged')
 start=symbol('_start',2)['value'];require(target==start and text['address']<=start<text['address']+text['size'],'Reset jump does not reach _start')
 for name in ('driver_data_init','pcm_control_loop'):require(text['address']<=symbol(name,2)['value']<text['address']+text['size'],'Function outside text '+name)
 arrays={};ranges=[];bss=byname['.bss']
 for name,size in contract['workspace']['required_array_symbol_sizes'].items():
  sy=symbol(name,1);require(sy['size']==size and sy['section']==bss['index']and bss['address']<=sy['value']and sy['value']+size<=bss['address']+bss['size'],'Array ABI/workspace '+name);arrays[name]=sy;ranges.append((sy['value'],sy['value']+size,name))
 for a,b in zip(sorted(ranges),sorted(ranges)[1:]):require(a[1]<=b[0],'Array workspace overlap')
 require(symbol('__bss_start')['value']==bss['address']and symbol('__bss_end')['value']==bss['address']+bss['size'],'BSS markers differ')
 end=(bss['address']+bss['size']+7)&~7
 require(symbol('_end')['value']==symbol('__end')['value']==end and end<=bound,'Aligned end crosses communication')
 globals={name:struct.unpack('>I',content(name,4))[0]for name in ('sh2Com','csr')}
 require(globals=={'sh2Com':contract['communication']['sh2Com_pointer_data_expected'],'csr':contract['communication']['csr_pointer_data_expected']},'Communication/register pointers changed')
 file_sections=[s for s in alloc if s['type']!=8];image=bytearray(max(s['address']+s['size']for s in file_sections))
 for sec in file_sections:image[sec['address']:sec['address']+sec['size']]=area(sec['offset'],sec['size'])
 return dict(status='ELF_metadata_passed_not_runtime_accepted',elf_sha256=sha(raw),elf_bytes=len(raw),entry=entry,flags=flags,sections=alloc,reset_jump=jump,reset_target=start,aligned_end=end,boundary_equality=end==bound,workspace_headroom=bound-end,array_symbols=arrays,communication=globals,predicted_SH2_pcmCtrl=0x25a00000+arrays['pcmCtrlData']['value'],flat_image_bytes=len(image),flat_image_sha256=sha(bytes(image)),undefined_symbols=[],target_executed=False)
