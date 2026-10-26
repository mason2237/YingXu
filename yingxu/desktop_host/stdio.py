"""Bounded private NDJSON input without BufferedReader shutdown locks."""
import json
import os
import sys


def frames(max_bytes=65536):
    buffer = bytearray()
    descriptor = sys.stdin.fileno()
    while True:
        try:block = os.read(descriptor, 65536)
        except OSError:return
        if not block:return
        buffer.extend(block)
        while b'\n' in buffer:
            line, _, rest = buffer.partition(b'\n');buffer = bytearray(rest)
            if len(line) > max_bytes:return
            try:yield json.loads(line)
            except (UnicodeDecodeError, ValueError, RecursionError):continue
        if len(buffer) > max_bytes:return
