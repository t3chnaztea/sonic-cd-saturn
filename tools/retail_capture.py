import struct
from native import IS_BROWSER
if IS_BROWSER:
 import browser_ctypes as C
 from native import backend
 backend().resetGenesis()
else:
 import ctypes as C
from pathlib import Path
# Pinned core is used offline only; it is never linked into the Saturn game.
lib=C.CDLL(str(Path('.deps/genesis-plus-gx/genesis_plus_gx_libretro.dylib').resolve()))
ENV=C.CFUNCTYPE(C.c_bool,C.c_uint,C.c_void_p);VID=C.CFUNCTYPE(None,C.c_void_p,C.c_uint,C.c_uint,C.c_size_t);AUD=C.CFUNCTYPE(C.c_size_t,C.c_void_p,C.c_size_t);ONE=C.CFUNCTYPE(None,C.c_int16,C.c_int16);POLL=C.CFUNCTYPE(None);INPUT=C.CFUNCTYPE(C.c_int16,C.c_uint,C.c_uint,C.c_uint,C.c_uint)
folder=str(Path('assets/private').resolve()).encode()
@ENV
def env(cmd,data):
 if cmd==15:
  v=C.cast(data,C.POINTER(C.c_char_p))
  if v[0]==b'genesis_plus_gx_pcm_volume':v[1]=b'30';return True
 if cmd in (9,31):C.cast(data,C.POINTER(C.c_char_p))[0]=folder;return True
 if cmd==10:return True
 if cmd==3:C.cast(data,C.POINTER(C.c_bool))[0]=False;return True
 return False
chunks=[]
@AUD
def aud(p,n):chunks.append(C.string_at(p,n*4));return n
callbacks=[env,VID(lambda *a:None),aud,ONE(lambda *a:None),POLL(lambda:None),INPUT(lambda *a:0)]
for name,cb in zip(['environment','video_refresh','audio_sample_batch','audio_sample','input_poll','input_state'],callbacks):getattr(lib,'retro_set_'+name)(cb)
lib.retro_init()
class Game(C.Structure):_fields_=[('path',C.c_char_p),('data',C.c_void_p),('size',C.c_size_t),('meta',C.c_char_p)]
