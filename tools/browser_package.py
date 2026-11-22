"""Rebuild linked programs and the fixed ISO layout from audited recipes.

This module has no compiler and contains no accepted game payload. The same
serializer runs during maintainer certification and inside Pyodide.
"""
import hashlib
import json
from pathlib import Path
import subprocess
from recipe_tables import materialize


def sha(data):return hashlib.sha256(data).hexdigest()


def assemble(row,literals,derived):
    result=bytearray(row['bytes']);at=0
    for op in row['ops']:
        size=op['length'];kind=op['kind']
        if kind=='zero':data=bytes(size)
        elif kind=='literal':data=literals[op['offset']:op['offset']+size]
        elif kind=='derive':data=derived(op)[op.get('offset',0):op.get('offset',0)+size]
        else:raise ValueError('Unsupported image construction operation')
        if len(data)!=size or at+size>len(result):raise ValueError('Invalid image construction range')
        result[at:at+size]=data;at+=size
    if at!=len(result)or sha(result)!=row['sha256']:raise ValueError('Constructed image checksum failed')
    return result


def build(root,manifest,literals):
    root=Path(root)
    for name,row in manifest['metadata'].items():
        path=root/name;path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(assemble(row,literals,lambda op:(_ for _ in ()).throw(ValueError('Invalid metadata derive'))))
    def table(op):return materialize(manifest['tables'][op['table']],root,manifest['tables'])
    for name,row in manifest['programs'].items():
        path=root/name;path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(assemble(row,literals,table))
    def file(op):
        if 'table'in op:return table(op)
        row=op['file'];data=(root/row['source']).read_bytes()
        if len(data)!=row['bytes']or sha(data)!=row['sha256']:raise ValueError('Converted CD file checksum failed: '+row['source'])
        return data
    iso=root/'build/browser/image.iso';iso.parent.mkdir(parents=True,exist_ok=True)
    iso.write_bytes(assemble(manifest['iso'],literals,file))
    raw=root/'build/browser/data.raw'
    subprocess.run(['iso_to_raw',str(iso),str(raw)],cwd=root,check=True)
    if raw.stat().st_size!=manifest['data_track']['bytes']or sha(raw.read_bytes())!=manifest['data_track']['sha256']:
        raise ValueError('Encoded data-track checksum failed')
    (root/'build/browser/pregap.raw').write_bytes(bytes(150*2352))
    return raw
