#!/usr/bin/env python3
"""Create an integrity-checked SQLite backup without stopping the app."""
import argparse
from contextlib import closing
import os
from pathlib import Path
import sqlite3
import tempfile


def backup(source, destination):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if not source.is_file(): raise ValueError('Source database does not exist.')
    if destination.exists(): raise ValueError('Choose a new backup filename; existing files are never overwritten.')
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.backup-', dir=destination.parent)
    os.close(fd)
    temporary = Path(name)
    try:
        with closing(sqlite3.connect(source.as_uri()+'?mode=ro', uri=True)) as original:
            with closing(sqlite3.connect(temporary)) as copied:
                original.backup(copied, pages=256)
                if copied.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise ValueError('Backup integrity check failed.')
        # Publish atomically without replacing an existing backup; keep mode 0600.
        os.link(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(backup(args.source, args.output))


if __name__ == '__main__': main()
