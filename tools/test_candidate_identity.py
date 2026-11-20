#!/usr/bin/env python3
"""Only ISO date fields may disappear from a candidate identity."""
import unittest
from candidate_identity import normalized_iso_sha256


def record(lba, size, name, directory=False):
    length = (33 + len(name) + 1) & ~1
    data = bytearray(length)
    data[0] = length
    data[2:10] = lba.to_bytes(4, 'little') + lba.to_bytes(4, 'big')
    data[10:18] = size.to_bytes(4, 'little') + size.to_bytes(4, 'big')
    data[18:25] = bytes([126, 10, 1, 1, 23, 0, 0])
    data[25] = 2 if directory else 0
    data[32], data[33:33 + len(name)] = len(name), name
    return data


def fixture():
    data = bytearray(20 * 2048)
    pvd, directory = 16 * 2048, 18 * 2048
    data[pvd:pvd + 7] = b'\x01CD001\x01'
    data[17 * 2048:17 * 2048 + 7] = b'\xffCD001\x01'
    data[pvd + 156:pvd + 190] = record(18, 2048, b'\0', True)
    rows = [record(18, 2048, b'\0', True), record(18, 2048, b'\1', True), record(19, 7, b'A.BIN;1')]
    for row in rows:
        data[directory:directory + len(row)] = row
        directory += len(row)
    data[19 * 2048:19 * 2048 + 7] = b'payload'
    return data


class IdentityTest(unittest.TestCase):
    def test_volume_and_directory_dates_only(self):
        a = fixture();b = bytearray(a)
        pvd = 16 * 2048
        b[pvd + 813:pvd + 881] = b'1' * 68
        for offset in [pvd + 156, 18 * 2048, 18 * 2048 + 34, 18 * 2048 + 68]:
            b[offset + 18:offset + 25] = b'2' * 7
        self.assertEqual(normalized_iso_sha256(a), normalized_iso_sha256(b))

    def test_boot_layout_names_payload_and_padding_remain_bound(self):
        a = fixture()
        for offset in [0, 16 * 2048 + 40, 18 * 2048 + 68 + 2,
                       18 * 2048 + 68 + 33, 19 * 2048, 19 * 2048 + 100]:
            with self.subTest(offset=offset):
                b = bytearray(a);b[offset] ^= 1
                self.assertNotEqual(normalized_iso_sha256(a), normalized_iso_sha256(b))

    def test_extensions_and_invalid_directories_fail_closed(self):
        for offset, value in [(16 * 2048, 2), (18 * 2048, 20)]:
            b = fixture();b[offset] = value
            with self.assertRaises(AssertionError):
                normalized_iso_sha256(b)


if __name__ == '__main__':
    unittest.main()
