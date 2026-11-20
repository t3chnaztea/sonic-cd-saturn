"""Loaded only when tools/scddisasm_audit.py puts this folder on PYTHONPATH."""
import os
import sys
if os.environ.get('SCD_AUDIT_DIR'):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import scddisasm_audit
    sys.path.pop(0)
    scddisasm_audit.install()
