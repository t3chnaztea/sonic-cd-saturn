"""Keep generated build inputs stable when their bytes have not changed."""
from pathlib import Path


def write_text(path, value):
    path = Path(path)
    data = value.encode()
    if not path.exists() or path.read_bytes() != data:
        path.write_bytes(data)


def write_bytes(path, data):
    path = Path(path)
    if not path.exists() or path.read_bytes() != data:
        path.write_bytes(data)


def copy_file(source, target):
    source, target = Path(source), Path(target)
    data = source.read_bytes()
    if not target.exists() or target.read_bytes() != data:
        target.write_bytes(data)
