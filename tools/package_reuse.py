"""Byte-checked reuse at the ISO/BIN packaging boundaries. No timestamp cache."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

CHUNK = 256 * 1024
SECTOR = 2352


def digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(CHUNK), b""):
            result.update(block)
    return result.hexdigest()


def sync_file(descriptor):
    os.fsync(descriptor)
    if sys.platform == "darwin":
        import fcntl
        fcntl.fcntl(descriptor, fcntl.F_FULLFSYNC)


def sync_parent(path):
    descriptor = os.open(Path(path).parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def cleanup(path, primary=None):
    try:
        Path(path).unlink()
    except FileNotFoundError:
        pass
    except OSError as error:
        if primary is None:
            raise
        primary.add_note("temporary cleanup failed: " + repr(error))


def temporary(path):
    path = Path(path)
    descriptor, name = tempfile.mkstemp(prefix="." + path.name + ".", suffix=".tmp",
                                       dir=path.parent)
    os.close(descriptor)
    return Path(name)


def stage_bytes(path, value):
    staged = temporary(path)
    try:
        with staged.open("wb") as stream:
            stream.write(value)
            stream.flush()
            sync_file(stream.fileno())
        return staged
    except BaseException as error:
        cleanup(staged, error)
        raise


def publish_package(changes):
    """Keep rollback links until every staged package file is published and synced."""
    if not changes:
        return
    changes = [(Path(target), Path(staged)) for target, staged in changes]
    parent = changes[0][0].parent
    if any(target.parent != parent or staged.parent != parent
           for target, staged in changes):
        raise ValueError("package staging must use the destination directory")
    rollback = Path(tempfile.mkdtemp(prefix=".package-rollback-", dir=parent))
    previous, published = {}, []
    restored = False
    try:
        for target, _ in changes:
            backup = rollback / target.name
            try:
                os.link(target, backup)
            except FileNotFoundError:
                if not parent.is_dir():
                    raise
                previous[target] = None
            else:
                previous[target] = backup
        sync_parent(rollback / "entry")
        for target, staged in changes:
            os.replace(staged, target)
            published.append(target)
            with target.open("rb") as stream:
                sync_file(stream.fileno())
            sync_parent(target)
    except BaseException as primary:
        failed = False
        for target in reversed(published):
            try:
                if previous[target] is None:
                    target.unlink()
                else:
                    os.replace(previous[target], target)
                sync_parent(target)
            except OSError as error:
                failed = True
                primary.add_note("package rollback failed; retained " +
                                 str(rollback) + ": " + repr(error))
        restored = not failed
        raise
    else:
        restored = True
    finally:
        primary = sys.exc_info()[1]
        if restored or not published:
            for backup in previous.values():
                if backup is not None:
                    cleanup(backup, primary)
            try:
                rollback.rmdir()
            except OSError as error:
                if primary is None:
                    raise
                primary.add_note("rollback directory cleanup failed: " + repr(error))


def iso_sectors(path):
    path = Path(path)
    size = path.stat().st_size
    if not size or size % 2048:
        raise ValueError("Unaligned or empty disc image")
    with path.open("rb") as stream:
        if stream.read(16) != b"SEGA SEGASATURN ":
            raise ValueError("Bad Saturn boot signature")
    return size // 2048


def audio_inputs(root, audio):
    tracks = audio["tracks"]
    if (len(tracks) != 41 or audio.get("music_source", {}).get("region") != "Japan"
            or any(not track.get("soundtrack", "").startswith("Japan")
                   for track in tracks)):
        raise ValueError("Japanese music is required")
    paths = []
    for index, track in enumerate(tracks):
        path = Path(root) / f"assets/generated/music{index}.raw"
        if (not isinstance(track["sectors"], int) or track["sectors"] < 1
                or path.stat().st_size != track["sectors"] * SECTOR
                or digest(path) != track["sha256"]):
            raise ValueError(f"Audio input mismatch: {index}")
        paths.append(path)
    return paths


def cue_layout(binary_name, sectors, tracks):
    text = f'FILE "{binary_name}" BINARY\n  TRACK 01 MODE1/2352\n    INDEX 01 00:00:00\n'
    laid_out = []
    msf = lambda n: f"{n // 4500:02d}:{n // 75 % 60:02d}:{n % 75:02d}"
    for index, original in enumerate(tracks):
        track = dict(original)
        text += f"  TRACK {index + 2:02d} AUDIO\n"
        if index == 0:
            text += f"    INDEX 00 {msf(sectors)}\n"
            sectors += 150
        text += f"    INDEX 01 {msf(sectors)}\n"
        track["bin_sector"] = sectors
        laid_out.append(track)
        sectors += track["sectors"]
    return text.encode(), laid_out, sectors * SECTOR


def binary_matches(encoder, iso, binary, tracks, music):
    binary = Path(binary)
    if len(tracks) != len(music):
        raise ValueError("Audio track/path count differs")
    try:
        stream = binary.open("rb")
    except FileNotFoundError:
        if not binary.parent.is_dir():
            raise
        return False
    with stream:
        result = subprocess.run([str(encoder), "--check-data", str(iso), str(binary)])
        if result.returncode not in (0, 2):
            raise subprocess.CalledProcessError(result.returncode, result.args)
        matches = result.returncode == 0
        stream.seek(iso_sectors(iso) * SECTOR)
        matches = stream.read(150 * SECTOR) == bytes(150 * SECTOR) and matches
        for track, path in zip(tracks, music):
            checksum = hashlib.sha256()
            count = 0
            with path.open("rb") as source:
                for block in iter(lambda: source.read(CHUNK), b""):
                    checksum.update(block)
                    count += len(block)
                    matches = stream.read(len(block)) == block and matches
            if count != track["sectors"] * SECTOR or checksum.hexdigest() != track["sha256"]:
                raise ValueError("Audio changed during package verification")
        return not stream.read(1) and matches


def append_audio(binary, tracks, music):
    with Path(binary).open("ab") as output:
        output.write(bytes(150 * SECTOR))
        for track, path in zip(tracks, music):
            checksum, count = hashlib.sha256(), 0
            with path.open("rb") as source:
                for block in iter(lambda: source.read(CHUNK), b""):
                    checksum.update(block)
                    count += len(block)
                    output.write(block)
            if count != track["sectors"] * SECTOR or checksum.hexdigest() != track["sha256"]:
                raise ValueError("Audio changed during package generation")
        output.flush()
        sync_file(output.fileno())


def _iso_stream(command, existing):
    """Consume the entire producer even after mismatching bytes or a disk-read error."""
    process = subprocess.Popen(command, stdout=subprocess.PIPE)
    checksum, matches, read_error = hashlib.sha256(), existing is not None, None
    try:
        for block in iter(lambda: process.stdout.read(CHUNK), b""):
            checksum.update(block)
            if existing is not None and read_error is None:
                try:
                    matches = existing.read(len(block)) == block and matches
                except OSError as error:
                    read_error = error
                    matches = False
        if existing is not None and read_error is None:
            try:
                matches = not existing.read(1) and matches
            except OSError as error:
                read_error = error
        process.stdout.close()
        status = process.wait()
    except BaseException as primary:
        try:
            process.stdout.close()
        except OSError as error:
            primary.add_note("producer pipe cleanup failed: " + repr(error))
        try:
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        except OSError as error:
            primary.add_note("producer cleanup failed: " + repr(error))
        raise
    if status:
        raise subprocess.CalledProcessError(status, command)
    if read_error is not None:
        raise read_error
    return matches, checksum.hexdigest()


def reuse_iso(real, arguments):
    positions = [index for index, value in enumerate(arguments)
                 if value in ("-o", "-output")]
    if len(positions) != 1 or positions[0] + 1 >= len(arguments):
        return subprocess.call([real, *arguments])
    index = positions[0] + 1
    if arguments[index] == "-":
        return subprocess.call([real, *arguments])
    output = Path(arguments[index]).absolute()
    stream_arguments = list(arguments)
    stream_arguments[index] = "-"
    try:
        existing = output.open("rb")
    except FileNotFoundError:
        if not output.parent.is_dir():
            raise
        existing = None
    try:
        matches, expected = _iso_stream([real, *stream_arguments], existing)
    finally:
        if existing is not None:
            existing.close()
    if matches:
        # Make still uses filesystem mtimes for dependency freshness. The ISO
        # contents were checked above; acknowledge the completed build without
        # rewriting the image or using a timestamp to decide byte identity.
        previous = output.stat()
        try:
            os.utime(output, None)
            with output.open("rb") as stream:
                sync_file(stream.fileno())
        except BaseException as primary:
            try:
                os.utime(output, ns=(previous.st_atime_ns, previous.st_mtime_ns))
                with output.open("rb") as stream:
                    sync_file(stream.fileno())
            except OSError as error:
                primary.add_note("ISO timestamp rollback failed: " + repr(error))
            raise
        print("Reused byte-identical ISO", flush=True)
        return 0
    staged = temporary(output)
    try:
        original_arguments = list(arguments)
        original_arguments[index] = str(staged)
        subprocess.run([real, *original_arguments], check=True)
        if digest(staged) != expected:
            raise ValueError("ISO file/stdout bytes differ or inputs changed during generation")
        with staged.open("rb") as stream:
            sync_file(stream.fileno())
        publish_package([(output, staged)])
    finally:
        cleanup(staged, sys.exc_info()[1])
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] != "iso":
        raise SystemExit("Usage: package_reuse.py iso XORRISOFS [arguments ...]")
    raise SystemExit(reuse_iso(sys.argv[2], sys.argv[3:]))
