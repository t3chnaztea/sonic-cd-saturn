'use strict';
// Emscripten-to-Emscripten file access without copying an entire disc into each
// emulator instance. Only the conversion workspace can be reached by a module.
const SonicPyFS = (() => {
  function mount(module, external, root = '/project') {
    const FS = module.FS;
    function fail() { throw new FS.ErrnoError(30); }
    function writable(path) {
      if (!['/project/build/', '/project/cd/', '/project/assets/generated/'].some(prefix => path.startsWith(prefix))) fail();
    }
    const type = {
      mount() { return node(null, '/', root); },
      node_ops: {
        getattr(n) { return external.stat(n.externalPath); },
        setattr(n, attr) {
          writable(n.externalPath);
          if (attr.size !== undefined) external.truncate(n.externalPath, attr.size);
        },
        lookup(parent, name) {
          const path = parent.externalPath + '/' + name;
          external.stat(path);
          return node(parent, name, path);
        },
        mknod(parent, name, mode) {
          const path = parent.externalPath + '/' + name; writable(path);
          if (FS.isDir(mode)) external.mkdir(path, mode);
          else external.close(external.open(path, 'w', mode));
          return node(parent, name, path);
        },
        readdir(n) { return external.readdir(n.externalPath); },
        readlink(n) { return external.readlink(n.externalPath); },
        unlink(parent, name) { const p = parent.externalPath + '/' + name; writable(p); external.unlink(p); },
        rmdir(parent, name) { const p = parent.externalPath + '/' + name; writable(p); external.rmdir(p); },
        rename() { fail(); }, symlink() { fail(); }
      },
      stream_ops: {
        open(stream) {
          if ((stream.flags & 3) !== 0 || (stream.flags & (64 | 512 | 1024))) writable(stream.node.externalPath);
          stream.externalStream = external.open(stream.node.externalPath, stream.flags);
        },
        close(stream) { external.close(stream.externalStream); },
        read(s, buffer, offset, length, position) { return external.read(s.externalStream, buffer, offset, length, position); },
        write(s, buffer, offset, length, position) { writable(s.node.externalPath); return external.write(s.externalStream, buffer, offset, length, position); },
        llseek(s, offset, whence) {
          let position = offset;
          if (whence === 1) position += s.position;
          else if (whence === 2) position += external.stat(s.node.externalPath).size;
          if (position < 0) throw new FS.ErrnoError(28);
          return position;
        }
      }
    };
    function node(parent, name, path) {
      const stat = external.stat(path), n = FS.createNode(parent, name, stat.mode, 0);
      n.externalPath = path; n.node_ops = type.node_ops; n.stream_ops = type.stream_ops;
      return n;
    }
    FS.mkdir(root); FS.mount(type, {}, root);
  }
  // FileReaderSync is Worker-only. No file is uploaded or read through a URL.
  function mountFiles(FS, directory, files) {
    const reader = new FileReaderSync();
    const denied = () => { throw new FS.ErrnoError(30); };
    const entries = new Map();
    for (const file of files) {
      if (!(file instanceof Blob) || !file.name || /[\\/\x00-\x1f]/.test(file.name) || entries.has(file.name)) throw Error('Invalid disc file selection.');
      entries.set(file.name, file);
    }
    const type = {
      mount() { return create(null, '/', null); },
      node_ops: {
        getattr(n) { return {dev:1,ino:n.id,mode:n.mode,nlink:1,uid:0,gid:0,rdev:0,size:n.blob ? n.blob.size : 4096,
          atime:new Date(0),mtime:new Date(0),ctime:new Date(0),blksize:4096,blocks:Math.ceil((n.blob?.size || 0)/4096)}; },
        lookup(parent, name) {
          if (!entries.has(name)) throw new FS.ErrnoError(44);
          return create(parent, name, entries.get(name));
        },
        readdir() { return ['.', '..', ...entries.keys()]; },
        setattr:denied, mknod:denied, rename:denied, unlink:denied, rmdir:denied, symlink:denied
      },
      stream_ops: {
        open(s) { if ((s.flags & 3) !== 0 || (s.flags & (64|512|1024))) denied(); },
        read(s, buffer, offset, length, position) {
          const n=s.node, count=Math.max(0,Math.min(length,n.blob.size-position));
          if (!count) return 0;
          if (!n.cache || position < n.cacheStart || position+count > n.cacheStart+n.cache.length) {
            n.cacheStart=position;
            n.cache=new Uint8Array(reader.readAsArrayBuffer(n.blob.slice(position,position+Math.max(count,1024*1024))));
          }
          buffer.set(n.cache.subarray(position-n.cacheStart,position-n.cacheStart+count),offset);
          return count;
        },
        llseek(s, offset, whence) {
          const position=offset+(whence===1?s.position:whence===2?s.node.blob.size:0);
          if(position<0) throw new FS.ErrnoError(28);
          return position;
        }, write:denied
      }
    };
    function create(parent,name,blob) {
      const n=FS.createNode(parent,name,(blob?0o100444:0o40555),0);
      n.blob=blob;n.node_ops=type.node_ops;n.stream_ops=type.stream_ops;return n;
    }
    FS.mkdirTree(directory);FS.mount(type,{},directory);
  }
  return {mount,mountFiles};
})();
if(typeof module!=='undefined')module.exports=SonicPyFS;
