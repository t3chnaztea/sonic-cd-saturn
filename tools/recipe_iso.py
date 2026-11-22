"""Read the accepted ISO9660 layout without retaining game file bytes."""
import hashlib
import struct
import json


def boot_blobs(root,image):
    """Do not assume the SDK's embedded boot/security binaries are owned code."""
    ip=(root/'build/saturn/IP.BIN').read_bytes()
    if image[:len(ip)]!=ip:raise ValueError('Accepted boot area differs from the linked IP')
    commit=json.loads((root/'sources.lock.json').read_text())['libyaul']['commit']
    result=[]
    for name in ['sys_sec.bin','sys_arej.bin','sys_aret.bin','sys_areu.bin','sys_aree.bin','sys_init.bin']:
        source='.deps/libyaul/libyaul/ip/blobs/'+name;data=(root/source).read_bytes()
        offset=ip.find(data)
        if offset<0 or ip.find(data,offset+1)>=0:raise ValueError('Boot blob has no unique accepted range')
        result.append(dict(source=source,offset=offset,bytes=len(data),sha256=digest(data),source_commit=commit))
    result.sort(key=lambda row:row['offset'])
    if any(a['offset']+a['bytes']>b['offset']for a,b in zip(result,result[1:])):raise ValueError('Boot blob ranges overlap')
    return result


def boot_tables(rows):
    return [dict(file='build/browser/image.iso',offset=row['offset'],bytes=row['bytes'],codec='reference-slice',
        source=row['source'],source_commit=row['source_commit'],source_offset=0,
        source_bytes=row['bytes'],source_sha256=row['sha256'],sha256=row['sha256'])for row in rows]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def catalog(image):
    if len(image)%2048 or image[32769:32774]!=b'CD001':
        raise ValueError('Expected a complete ISO9660 image')
    files=[];directories=[];visited=set()
    def walk(record,parent):
        sector=struct.unpack_from('<I',record,2)[0]
        length=struct.unpack_from('<I',record,10)[0]
        if (sector,length)in visited:raise ValueError('Repeated directory extent')
        visited.add((sector,length));directories.append((sector*2048,length))
        start=sector*2048;at=0
        while at<length:
            size=image[start+at]
            if not size:at=((at//2048)+1)*2048;continue
            row=image[start+at:start+at+size]
            if len(row)!=size or size<34:raise ValueError('Invalid directory record')
            at+=size;name=row[33:33+row[32]]
            if name in (b'\0',b'\1'):continue
            name=name.decode('ascii').split(';')[0]
            if '/'in name or name in ('.','..'):raise ValueError('Unsafe ISO filename')
            path=parent+name
            if row[25]&2:walk(row,path+'/');continue
            offset=struct.unpack_from('<I',row,2)[0]*2048
            count=struct.unpack_from('<I',row,10)[0]
            if offset+count>len(image):raise ValueError('ISO file exceeds image')
            files.append(dict(source='cd/'+path,offset=offset,bytes=count,
                              sha256=digest(image[offset:offset+count])))
    walk(image[32768+156:32768+190],'')
    spans=sorted((r['offset'],r['offset']+r['bytes'])for r in files if r['bytes'])
    if any(left[1]>right[0]for left,right in zip(spans,spans[1:])):
        raise ValueError('Overlapping ISO files')
    return dict(bytes=len(image),sha256=digest(image),files=files,
                directories=[dict(offset=a,bytes=b)for a,b in directories])


def structure(image,layout):
    result=bytearray(image)
    for row in layout['files']:
        result[row['offset']:row['offset']+row['bytes']]=bytes(row['bytes'])
    return bytes(result)
