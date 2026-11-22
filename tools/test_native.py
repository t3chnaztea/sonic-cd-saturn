#!/usr/bin/env python3
"""Desktop subprocess boundary contracts; no game assets or host tools required."""
import os
import subprocess
import sys
import unittest
import native


class DesktopBoundary(unittest.TestCase):
    def test_import_does_not_patch_stdlib(self):
        self.assertFalse(native.IS_BROWSER)
        self.assertIs(subprocess.run, native._desktop_run)

    def test_binary_stdout_and_nonzero_status(self):
        command = [sys.executable, '-c', 'import sys;sys.stdout.buffer.write(bytes([0,255]));sys.exit(7)']
        result = native.run(command, capture_output=True)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (7, b'\0\xff', b''))
        with self.assertRaises(subprocess.CalledProcessError) as error:
            native.run(command, capture_output=True, check=True)
        self.assertEqual(error.exception.output, b'\0\xff')

    def test_text_environment_and_stderr(self):
        result = native.run([sys.executable, '-c',
            'import os,sys;print(os.environ["PATCHER_BOUNDARY_TEST"]);print("diagnostic",file=sys.stderr)'],
            capture_output=True, text=True, env=dict(os.environ, PATCHER_BOUNDARY_TEST='local'))
        self.assertEqual((result.stdout, result.stderr), ('local\n', 'diagnostic\n'))

    def test_browser_install_cannot_run_on_desktop(self):
        with self.assertRaisesRegex(RuntimeError, 'requires Pyodide'):
            native.install(object())
        self.assertIs(subprocess.run, native._desktop_run)


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(DesktopBoundary)
    if not unittest.TextTestRunner(verbosity=1).run(suite).wasSuccessful():
        raise SystemExit(1)
    print('PASS: native boundary; desktop subprocess semantics preserved')
