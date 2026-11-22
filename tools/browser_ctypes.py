"""The small ctypes surface used by the retail capture tools, over WASM memory.

Addresses refer to the Genesis module, never Pyodide's linear memory. The
desktop tools continue to use real ctypes. This module never loads a dylib.
"""
import struct
from native import backend


class Kind:
    def __init__(self, size, signed=False):
        self.size, self.signed = size, signed

    def __mul__(self, count):
        kind = self

        class Array:
            @classmethod
            def in_dll(cls, lib, name):
                return Memory(int(backend().symbol(name)), count, kind)
        return Array

    def in_dll(self, lib, name):
        return Memory(int(backend().symbol(name)), 1, self)

    def from_address(self, address):
        return Memory(address, 1, self)


class Memory:
    def __init__(self, address, count, kind):
        self.address, self.count, self.kind = address, count, kind

    def __getitem__(self, index):
        if isinstance(index, slice):
            return [self[n] for n in range(*index.indices(self.count))]
        if not 0 <= index < self.count:
            raise IndexError(index)
        return int.from_bytes(string_at(self.address + index*self.kind.size, self.kind.size),
                              'little', signed=self.kind.signed)

    def __setitem__(self, index, value):
        if not 0 <= index < self.count:
            raise IndexError(index)
        memmove(self.address + index*self.kind.size,
                int(value).to_bytes(self.kind.size, 'little', signed=self.kind.signed), self.kind.size)

    @property
    def value(self):
        return self[0]


c_uint8 = Kind(1)
c_uint16 = Kind(2)
c_uint = Kind(4)
c_int16 = Kind(2, True)
c_int = Kind(4, True)
c_bool = Kind(1)
c_void_p = Kind(4)
c_char_p = Kind(4)
c_size_t = Kind(4)


class Structure:
    def __init__(self, *values):
        for (name, _), value in zip(self._fields_, values):
            setattr(self, name, value)


def CFUNCTYPE(*signature):
    return lambda function: function


def POINTER(kind):
    return kind


def byref(value):
    return value


def addressof(value):
    return value.address


def string_at(address, length):
    result = bytearray(length)
    backend().readMemoryInto(int(address), result)
    return bytes(result)


def memmove(destination, source, length):
    address = destination.address if isinstance(destination, Memory) else int(destination)
    data = string_at(source, length) if isinstance(source, int) else bytes(source)[:length]
    backend().writeMemory(address, data)


class Function:
    def __init__(self, name):
        self.name = name
        self.argtypes = self.restype = None

    def __call__(self, *args):
        api = backend()
        if self.name.startswith('retro_set_') and self.name in (
                'retro_set_environment', 'retro_set_video_refresh', 'retro_set_audio_sample_batch',
                'retro_set_audio_sample', 'retro_set_input_poll', 'retro_set_input_state'):
            api.callback(self.name, args[0])
            return None
        if self.name == 'retro_load_game':
            return bool(api.loadGame(args[0].path.decode()))
        return api.call(self.name, list(args))


class CDLL:
    def __init__(self, ignored_path):
        self.functions = {}

    def __getattr__(self, name):
        if name not in self.functions:
            self.functions[name] = Function(name)
        return self.functions[name]
